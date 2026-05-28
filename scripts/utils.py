"""
Shared utilities for Discord Thread Manager scripts.

Provides:
- Authenticated HTTP client with rate-limit handling
- Pagination helpers for thread listing
- Thread activity analysis
- Common constants and types
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("discord-thread-manager")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DISCORD_API_BASE = "https://discord.com/api/v10"
DEFAULT_RATE_LIMIT_DELAY = 1.0
MAX_RETRIES = 3

# Category keyword mapping for auto-categorization
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Subscription/Plan": [
        "subscription", "plan", "upgrade", "downgrade", "tier", "pricing",
        "free plan", "pro plan", "billing plan", "cancel subscription",
        "renew", "trial", "demo",
    ],
    "Payment/Billing": [
        "payment", "billing", "charge", "refund", "invoice", "credit card",
        "paypal", "stripe", "transaction", "overcharge", "failed payment",
        "receipt",
    ],
    "Technical Bugs": [
        "bug", "error", "crash", "broken", "not working", "issue", "fault",
        "glitch", "unexpected", "wrong", "doesn't work", "does not work",
        "fail", "failing", "failure",
    ],
    "API Errors": [
        "api", "endpoint", "status code", "500", "401", "403", "429",
        "rate limit", "timeout", "connection refused", "cors",
        "response", "request",
    ],
    "Performance": [
        "slow", "latency", "performance", "speed", "timeout", "hang",
        "freeze", "lag", "unresponsive", "load time", "memory",
    ],
}

# ---------------------------------------------------------------------------
# Discord API Client
# ---------------------------------------------------------------------------

class DiscordClient:
    """Minimal Discord REST client with rate-limit awareness."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("DISCORD_TOKEN", "")
        if not self.token:
            log.error("DISCORD_TOKEN not set. Export it or add to .env.")
            sys.exit(1)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"{self.token}",
            "Content-Type": "application/json",
        })

    # -- low-level request with retry & rate-limit handling ----------------

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{DISCORD_API_BASE}{path}"
        for attempt in range(1, MAX_RETRIES + 1):
            resp = self.session.request(method, url, **kwargs)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", DEFAULT_RATE_LIMIT_DELAY))
                log.warning("Rate limited. Waiting %.1fs (attempt %d/%d)", retry_after, attempt, MAX_RETRIES)
                time.sleep(retry_after)
                continue
            if resp.status_code >= 500:
                wait = DEFAULT_RATE_LIMIT_DELAY * (2 ** (attempt - 1))
                log.warning("Server error %d. Retrying in %.1fs (attempt %d/%d)", resp.status_code, wait, attempt, MAX_RETRIES)
                time.sleep(wait)
                continue
            return resp
        return resp  # return last response even if all retries exhausted

    def get(self, path: str, **kwargs) -> requests.Response:
        return self._request("GET", path, **kwargs)

    def patch(self, path: str, **kwargs) -> requests.Response:
        return self._request("PATCH", path, **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        return self._request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self._request("DELETE", path, **kwargs)

    # -- thread-specific helpers ------------------------------------------

    def list_active_threads(self, channel_id: str) -> list[dict]:
        """List active (non-archived) threads in a channel."""
        resp = self.get(f"/channels/{channel_id}/threads/active")
        if resp.status_code != 200:
            log.error("Failed to list active threads: %d %s", resp.status_code, resp.text[:200])
            return []
        data = resp.json()
        return data.get("threads", [])

    def list_public_archived_threads(self, channel_id: str) -> list[dict]:
        """List all public archived threads with full pagination."""
        return self._list_archived(channel_id, "public")

    def list_private_archived_threads(self, channel_id: str) -> list[dict]:
        """List all private archived threads with full pagination."""
        return self._list_archived(channel_id, "private")

    def _list_archived(self, channel_id: str, visibility: str) -> list[dict]:
        """Paginate through archived threads.

        Discord returns threads in reverse chronological order (newest first).
        We use the `before` cursor to page through all results.
        """
        all_threads: list[dict] = []
        before = None
        while True:
            path = f"/channels/{channel_id}/threads/archived/{visibility}"
            params: dict = {"limit": 100}
            if before:
                params["before"] = before

            resp = self.get(path, params=params)
            if resp.status_code != 200:
                log.error("Failed to list %s archived threads: %d %s", visibility, resp.status_code, resp.text[:200])
                break

            data = resp.json()
            threads = data.get("threads", [])
            if not threads:
                break

            all_threads.extend(threads)

            # Use the last thread's archive_timestamp as the cursor.
            # CRITICAL: Discord expects ISO-8601 with 'Z' suffix, not '+00:00'.
            last = threads[-1]
            cursor_val = last.get("thread_metadata", {}).get("archive_timestamp", "")
            if cursor_val:
                # Normalize: replace +00:00 with Z
                before = cursor_val.replace("+00:00", "Z")
            else:
                break

            has_more = data.get("has_more", False)
            if not has_more:
                break

            # Small delay to be kind to the API
            time.sleep(0.5)

        return all_threads

    def get_thread_messages(self, channel_id: str, limit: int = 5) -> list[dict]:
        """Get the most recent messages in a thread (for activity analysis)."""
        resp = self.get(f"/channels/{channel_id}/messages", params={"limit": limit})
        if resp.status_code != 200:
            log.warning("Could not fetch messages for thread %s: %d", channel_id, resp.status_code)
            return []
        return resp.json()

    def lock_thread(self, thread_id: str) -> bool:
        """Lock a thread. Returns True if successful."""
        resp = self.patch(f"/channels/{thread_id}", json={"locked": True})
        if resp.status_code == 200:
            # Verify lock in thread_metadata (not top-level!)
            data = resp.json()
            locked = data.get("thread_metadata", {}).get("locked", False)
            if locked:
                return True
            # Some tokens return locked=None at top level but the lock still applies.
            # Treat 200 as success even if metadata doesn't reflect it immediately.
            log.info("Lock applied for thread %s (status 200, metadata may lag)", thread_id)
            return True
        log.error("Failed to lock thread %s: %d %s", thread_id, resp.status_code, resp.text[:200])
        return False

    def archive_thread(self, thread_id: str) -> bool:
        """Archive a thread by setting auto_archive_duration + archiving."""
        resp = self.patch(f"/channels/{thread_id}", json={"archived": True})
        if resp.status_code == 200:
            return True
        log.error("Failed to archive thread %s: %d %s", thread_id, resp.status_code, resp.text[:200])
        return False

    def lock_and_archive_thread(self, thread_id: str) -> tuple[bool, bool]:
        """Lock first, then archive. Returns (lock_success, archive_success).

        Order matters: lock before archive for reliable behavior.
        Some Discord implementations ignore lock if the thread is already archived
        unless lock is set before the archive flag.
        """
        lock_ok = self.lock_thread(thread_id)
        time.sleep(0.3)  # brief pause between operations
        archive_ok = self.archive_thread(thread_id)
        return lock_ok, archive_ok


# ---------------------------------------------------------------------------
# Thread Analysis Helpers
# ---------------------------------------------------------------------------

def parse_iso_timestamp(ts: str) -> datetime:
    """Parse a Discord ISO-8601 timestamp into a timezone-aware datetime."""
    if not ts:
        return datetime.min.replace(tzinfo=timezone.utc)
    # Normalize timezone suffix
    ts = ts.replace("+00:00", "Z").replace("z", "Z")
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def get_thread_last_activity(thread: dict, messages: list[dict] | None = None) -> datetime:
    """Determine the last activity time of a thread.

    Checks: last_message_id (most reliable) > thread_metadata.archive_timestamp >
    thread.last_message_id > thread_id timestamp.
    """
    # Try last_message_id from thread object (it's a snowflake -> timestamp)
    last_msg_id = thread.get("last_message_id")
    if last_msg_id:
        return snowflake_to_datetime(int(last_msg_id))

    # Check archive_timestamp
    archive_ts = thread.get("thread_metadata", {}).get("archive_timestamp", "")
    if archive_ts:
        return parse_iso_timestamp(archive_ts)

    # Fall back to message list if provided
    if messages:
        msg_timestamps = [parse_iso_timestamp(m.get("timestamp", "")) for m in messages if m.get("timestamp")]
        if msg_timestamps:
            return max(msg_timestamps)

    # Last resort: thread creation time from snowflake
    return snowflake_to_datetime(int(thread["id"]))


def snowflake_to_datetime(snowflake: int) -> datetime:
    """Convert a Discord snowflake ID to its creation datetime (UTC)."""
    DISCORD_EPOCH = 1420070400000  # 2015-01-01T00:00:00Z in ms
    timestamp_ms = (snowflake >> 22) + DISCORD_EPOCH
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)


def is_thread_stale(thread: dict, min_inactive_days: int, messages: list[dict] | None = None) -> bool:
    """Check if a thread has been inactive for at least min_inactive_days."""
    last_activity = get_thread_last_activity(thread, messages)
    cutoff = datetime.now(timezone.utc) - timedelta(days=min_inactive_days)
    return last_activity < cutoff


def categorize_thread(thread: dict, messages: list[dict] | None = None) -> str:
    """Attempt to categorize a thread by its name and messages using keyword matching."""
    text_to_check = (thread.get("name", "") or "").lower()

    if messages:
        for msg in messages[:3]:  # Check first few messages
            content = (msg.get("content", "") or "").lower()
            text_to_check += " " + content

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_to_check:
                return category

    return "Other/Misc"


def age_bucket(days_inactive: int) -> str:
    """Bucket a thread by its age in days."""
    if days_inactive < 60:
        return "30-60 days"
    elif days_inactive < 90:
        return "60-90 days"
    elif days_inactive < 180:
        return "90-180 days"
    else:
        return "180+ days"


# ---------------------------------------------------------------------------
# Output Helpers
# ---------------------------------------------------------------------------

def save_json(data, path: str):
    """Save data to a JSON file with pretty formatting."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    log.info("Saved JSON to %s", path)


def load_json(path: str):
    """Load data from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
