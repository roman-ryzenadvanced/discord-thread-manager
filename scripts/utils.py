"""
Shared utilities for Discord Thread Manager — Hacky Edition.

Thread analysis helpers, categorization, and output utilities.
No token management here — that's all handled by discord_controller.py.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log = logging.getLogger("discord-hacky")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DISCORD_EPOCH_MS = 1420070400000

CATEGORY_KEYWORDS = {
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
# Thread Analysis
# ---------------------------------------------------------------------------

def parse_iso_timestamp(ts: str) -> datetime:
    if not ts:
        return datetime.min.replace(tzinfo=timezone.utc)
    ts = ts.replace("+00:00", "Z").replace("z", "Z")
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def snowflake_to_datetime(snowflake: int) -> datetime:
    ts_ms = (snowflake >> 22) + DISCORD_EPOCH_MS
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)


def get_thread_last_activity(thread: dict, messages: list = None) -> datetime:
    last_msg_id = thread.get("last_message_id")
    if last_msg_id:
        return snowflake_to_datetime(int(last_msg_id))
    archive_ts = thread.get("thread_metadata", {}).get("archive_timestamp", "")
    if archive_ts:
        return parse_iso_timestamp(archive_ts)
    if messages:
        timestamps = [parse_iso_timestamp(m.get("timestamp", "")) for m in messages if m.get("timestamp")]
        if timestamps:
            return max(timestamps)
    return snowflake_to_datetime(int(thread["id"]))


def is_thread_stale(thread: dict, min_inactive_days: int, messages: list = None) -> bool:
    last_activity = get_thread_last_activity(thread, messages)
    cutoff = datetime.now(timezone.utc) - timedelta(days=min_inactive_days)
    return last_activity < cutoff


def categorize_thread(thread: dict, messages: list = None) -> str:
    text = (thread.get("name", "") or "").lower()
    if messages:
        for msg in messages[:3]:
            text += " " + (msg.get("content", "") or "").lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return category
    return "Other/Misc"


def age_bucket(days_inactive: int) -> str:
    if days_inactive < 60: return "30-60 days"
    elif days_inactive < 90: return "60-90 days"
    elif days_inactive < 180: return "90-180 days"
    else: return "180+ days"


# ---------------------------------------------------------------------------
# Output Helpers
# ---------------------------------------------------------------------------

def save_json(data, path: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    log.info("Saved JSON to %s", path)


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
