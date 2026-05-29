#!/usr/bin/env python3
"""
Discord Controller — The Hacky Way.

No bot tokens. No Discord developer portal. No OAuth setup.
Launches Discord with Chrome DevTools Protocol (CDP) debugging enabled,
connects to the live renderer process, and extracts your user token
from the running session via JavaScript injection.

Then uses that token to hit the Discord REST API directly,
plus CDP for DOM manipulation and xdotool as a last-resort fallback.

Prerequisites:
    - Discord desktop app installed on Linux
    - Python 3.9+
    - `requests`, `websocket-client` packages
    - `xdotool` for UI automation fallback (optional)

Usage:
    from discord_controller import DiscordController
    ctrl = DiscordController()          # launches discord, extracts token
    ctrl.scan_threads(channel_id)       # REST API via extracted token
    ctrl.lock_thread(thread_id)         # REST API
    ctrl.click_element(selector)        # CDP DOM
    ctrl.send_keys("Hello!")            # xdotool fallback

⚠️  WARNING: This uses your user account token, which is technically
    against Discord's Terms of Service. Use at your own risk.
    This was built for personal server management on Ubuntu Linux.
"""

import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import requests

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("discord-hacky")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CDP_PORT = 9222
DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_EPOCH_MS = 1420070400000  # 2015-01-01T00:00:00Z in ms

DISCORD_PATHS = [
    "/snap/discord/current/usr/share/discord/Discord",  # snap (most common on Ubuntu)
    "/usr/share/discord/Discord",           # deb install
    "/opt/Discord/Discord",                  # tar install
    os.path.expanduser("~/.local/share/Discord/Discord"),  # user install
    "discord",                               # PATH fallback
]

# Snap data dirs where Discord stores config
DISCORD_DATA_DIRS = [
    os.path.expanduser("~/.config/discord"),
    os.path.expanduser("~/snap/discord/current/.config/discord"),
    os.path.expanduser("~/snap/discord/285/.config/discord"),
]


# ---------------------------------------------------------------------------
# CDP (Chrome DevTools Protocol) Client
# ---------------------------------------------------------------------------

class CDPClient:
    """Minimal CDP client for connecting to Discord's renderer via WebSocket."""

    def __init__(self, port: int = CDP_PORT):
        self.port = port
        self.ws: Optional[object] = None
        self._msg_id = 0
        self._connected = False

    def _get_debug_url(self) -> str:
        """Fetch the WebSocket debug URL from Discord's CDP endpoint."""
        resp = requests.get(f"http://127.0.0.1:{self.port}/json")
        if resp.status_code != 200:
            raise ConnectionError(f"CDP endpoint returned {resp.status_code}")
        targets = resp.json()
        # Find the main Discord renderer target
        for target in targets:
            title = target.get("title", "").lower()
            url = target.get("url", "").lower()
            if "discord" in title or "discord" in url:
                return target["webSocketDebuggerUrl"]
        # Fallback: use the first page target
        for target in targets:
            if target.get("type") == "page":
                return target["webSocketDebuggerUrl"]
        if targets:
            return targets[0]["webSocketDebuggerUrl"]
        raise ConnectionError("No CDP targets found")

    def connect(self) -> bool:
        """Connect to Discord's renderer via CDP WebSocket."""
        if not HAS_WEBSOCKET:
            log.error("websocket-client not installed. Run: pip install websocket-client")
            return False
        try:
            ws_url = self._get_debug_url()
            self.ws = websocket.create_connection(ws_url, timeout=10)
            self._connected = True
            log.info("Connected to Discord renderer via CDP")
            return True
        except Exception as e:
            log.error("Failed to connect via CDP: %s", e)
            return False

    def evaluate(self, expression: str, timeout: float = 10.0) -> Optional[object]:
        """Evaluate JavaScript in the Discord renderer and return the result."""
        if not self._connected or not self.ws:
            return None
        self._msg_id += 1
        msg = json.dumps({
            "id": self._msg_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": False,
            }
        })
        try:
            self.ws.send(msg)
            self.ws.settimeout(timeout)
            response = json.loads(self.ws.recv())
            result = response.get("result", {}).get("result", {})
            if result.get("type") == "object" and result.get("subtype") == "error":
                log.warning("JS evaluation error: %s", result.get("description", ""))
                return None
            return result.get("value")
        except Exception as e:
            log.warning("CDP evaluate failed: %s", e)
            return None

    def extract_token(self) -> Optional[str]:
        """Extract the user's Discord token from the running session.

        Strategy:
        1. Try localStorage (Discord stores the token there in some builds)
        2. Fall back to parsing script tags for embedded token data
        3. Fall back to intercepting window.__SENTRY__/webpack cache
        """
        log.info("Attempting to extract Discord token from live session...")

        # Method 1: localStorage
        token = self.evaluate('localStorage.getItem("token")')
        if token and isinstance(token, str) and len(token) > 30:
            # Discord wraps tokens in quotes sometimes
            token = token.strip('"').strip("'")
            log.info("✓ Token extracted from localStorage")
            return token

        # Method 2: Parse script tags for embedded tokens
        token = self.evaluate("""
            (function() {
                var scripts = document.querySelectorAll('script');
                for (var i = 0; i < scripts.length; i++) {
                    var text = scripts[i].textContent;
                    if (text) {
                        var match = text.match(/"token"\\s*:\\s*"([^"]{30,})"/);
                        if (match) return match[1];
                    }
                }
                return null;
            })()
        """)
        if token and isinstance(token, str) and len(token) > 30:
            log.info("✓ Token extracted from script tags")
            return token

        # Method 3: webpack module cache (Discord uses webpack)
        token = self.evaluate("""
            (function() {
                try {
                    var cache = window.webpackChunkdiscord_app;
                    if (!cache) return null;
                    // Search through loaded modules for token
                    var modules = Object.keys(window).filter(k => k.startsWith('__'));
                    for (var i = 0; i < modules.length; i++) {
                        try {
                            var val = window[modules[i]];
                            if (val && typeof val === 'object') {
                                var keys = Object.keys(val);
                                for (var j = 0; j < keys.length; j++) {
                                    var item = val[keys[j]];
                                    if (item && item.exports) {
                                        var exp = item.exports;
                                        if (exp.default && typeof exp.default.getToken === 'function') {
                                            return exp.default.getToken();
                                        }
                                    }
                                }
                            }
                        } catch(e) {}
                    }
                } catch(e) {}
                return null;
            })()
        """)
        if token and isinstance(token, str) and len(token) > 30:
            log.info("✓ Token extracted from webpack cache")
            return token

        log.error("Failed to extract token from any method")
        return None

    def click_element(self, selector: str) -> bool:
        """Click a DOM element via CDP."""
        result = self.evaluate(f"""
            (function() {{
                var el = document.querySelector('{selector}');
                if (el) {{ el.click(); return true; }}
                return false;
            }})()
        """)
        return result is True

    def get_element_text(self, selector: str) -> Optional[str]:
        """Get text content of a DOM element via CDP."""
        return self.evaluate(f"""
            (function() {{
                var el = document.querySelector('{selector}');
                return el ? el.textContent : null;
            }})()
        """)

    def type_in_element(self, selector: str, text: str) -> bool:
        """Type text into a DOM element via CDP."""
        result = self.evaluate(f"""
            (function() {{
                var el = document.querySelector('{selector}');
                if (el) {{
                    el.focus();
                    el.value = '{text.replace("'", "\\'")}';
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }}
                return false;
            }})()
        """)
        return result is True

    def close(self):
        """Close the CDP WebSocket connection."""
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        self._connected = False


# ---------------------------------------------------------------------------
# xdotool Fallback for UI Automation
# ---------------------------------------------------------------------------

class XDoToolFallback:
    """Use xdotool for UI automation when CDP/DOM methods fail."""

    @staticmethod
    def is_available() -> bool:
        try:
            subprocess.run(["xdotool", "--version"], capture_output=True, check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    @staticmethod
    def find_discord_window() -> Optional[str]:
        """Find the Discord window ID."""
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", "Discord"],
                capture_output=True, text=True
            )
            windows = result.stdout.strip().split('\n')
            return windows[0] if windows and windows[0] else None
        except Exception:
            return None

    @staticmethod
    def activate_discord() -> bool:
        """Bring Discord window to foreground."""
        try:
            subprocess.run(["xdotool", "search", "--name", "Discord", "windowactivate"], check=True)
            time.sleep(0.5)
            return True
        except Exception:
            return False

    @staticmethod
    def send_keys(text: str) -> bool:
        """Send keystrokes to the active window."""
        try:
            subprocess.run(["xdotool", "type", "--delay", "50", text], check=True)
            return True
        except Exception:
            return False

    @staticmethod
    def send_key(key: str) -> bool:
        """Send a single key press (e.g., Return, Escape)."""
        try:
            subprocess.run(["xdotool", "key", key], check=True)
            return True
        except Exception:
            return False

    @staticmethod
    def click_at(x: int, y: int) -> bool:
        """Click at screen coordinates."""
        try:
            subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", "1"], check=True)
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Discord REST API Client (using extracted user token)
# ---------------------------------------------------------------------------

class DiscordAPIClient:
    """Discord REST API client using the extracted user token."""

    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        # User token auth (not "Bot " prefix)
        self.session.headers.update({
            "Authorization": token,
            "Content-Type": "application/json",
        })

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{DISCORD_API_BASE}{path}"
        for attempt in range(1, 4):
            resp = self.session.request(method, url, **kwargs)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 1.0))
                log.warning("Rate limited. Waiting %.1fs", retry_after)
                time.sleep(retry_after)
                continue
            if resp.status_code >= 500:
                wait = 1.0 * (2 ** (attempt - 1))
                log.warning("Server error %d. Retry in %.1fs", resp.status_code, wait)
                time.sleep(wait)
                continue
            return resp
        return resp

    def get(self, path: str, **kwargs) -> requests.Response:
        return self._request("GET", path, **kwargs)

    def patch(self, path: str, **kwargs) -> requests.Response:
        return self._request("PATCH", path, **kwargs)

    # -- Thread Operations --------------------------------------------------

    def list_active_threads(self, channel_id: str) -> list:
        resp = self.get(f"/channels/{channel_id}/threads/active")
        if resp.status_code != 200:
            log.error("Failed to list active threads: %d", resp.status_code)
            return []
        return resp.json().get("threads", [])

    def list_public_archived_threads(self, channel_id: str) -> list:
        all_threads = []
        cursor = None
        while True:
            params = {"limit": 100}
            if cursor:
                params["before"] = cursor
            resp = self.get(f"/channels/{channel_id}/threads/archived/public", params=params)
            if resp.status_code != 200:
                break
            data = resp.json()
            threads = data.get("threads", [])
            if not threads:
                break
            all_threads.extend(threads)
            cursor = threads[-1].get("thread_metadata", {}).get("archive_timestamp")
            if not cursor:
                break
            cursor = cursor.replace("+00:00", "Z")
        return all_threads

    def list_private_archived_threads(self, channel_id: str) -> list:
        all_threads = []
        cursor = None
        while True:
            params = {"limit": 100}
            if cursor:
                params["before"] = cursor
            resp = self.get(f"/channels/{channel_id}/threads/archived/private", params=params)
            if resp.status_code != 200:
                break
            data = resp.json()
            threads = data.get("threads", [])
            if not threads:
                break
            all_threads.extend(threads)
            cursor = threads[-1].get("thread_metadata", {}).get("archive_timestamp")
            if not cursor:
                break
            cursor = cursor.replace("+00:00", "Z")
        return all_threads

    def get_thread_messages(self, thread_id: str, limit: int = 5) -> list:
        resp = self.get(f"/channels/{thread_id}/messages", params={"limit": limit})
        if resp.status_code != 200:
            return []
        return resp.json()

    def lock_thread(self, thread_id: str) -> bool:
        resp = self.patch(f"/channels/{thread_id}", json={"locked": True})
        if resp.status_code == 200:
            log.info("Locked thread %s", thread_id)
            return True
        log.error("Failed to lock thread %s: %d", thread_id, resp.status_code)
        return False

    def archive_thread(self, thread_id: str) -> bool:
        resp = self.patch(f"/channels/{thread_id}", json={"archived": True})
        if resp.status_code == 200:
            return True
        log.error("Failed to archive thread %s: %d", thread_id, resp.status_code)
        return False

    def lock_and_archive(self, thread_id: str) -> tuple:
        """Lock first, then archive. Order matters for reliable behavior."""
        lock_ok = self.lock_thread(thread_id)
        time.sleep(0.3)
        archive_ok = self.archive_thread(thread_id)
        return lock_ok, archive_ok

    def send_message(self, channel_id: str, content: str) -> bool:
        resp = self._request("POST", f"/channels/{channel_id}/messages",
                            json={"content": content})
        return resp.status_code == 200

    # -- Guild / Channel Operations -----------------------------------------

    def list_guild_channels(self, guild_id: str) -> list:
        resp = self.get(f"/guilds/{guild_id}/channels")
        if resp.status_code != 200:
            return []
        return resp.json()

    def get_channel(self, channel_id: str) -> Optional[dict]:
        resp = self.get(f"/channels/{channel_id}")
        if resp.status_code == 200:
            return resp.json()
        return None

    @property
    def user_info(self) -> Optional[dict]:
        resp = self.get("/users/@me")
        if resp.status_code == 200:
            return resp.json()
        return None


# ---------------------------------------------------------------------------
# Main Controller
# ---------------------------------------------------------------------------

class DiscordController:
    """The main controller — orchestrates everything.

    Usage:
        ctrl = DiscordController()
        ctrl.launch()          # Start Discord with CDP
        ctrl.connect_cdp()     # Connect to renderer
        ctrl.extract_token()   # Yank the token
        # Now use ctrl.api for REST, ctrl.cdp for DOM, ctrl.xdo for xdotool
    """

    def __init__(self, cdp_port: int = CDP_PORT):
        self.cdp_port = cdp_port
        self.cdp = CDPClient(cdp_port)
        self.api: Optional[DiscordAPIClient] = None
        self.xdo = XDoToolFallback()
        self._discord_process: Optional[subprocess.Popen] = None
        self._token: Optional[str] = None

    @property
    def token(self) -> Optional[str]:
        return self._token

    def launch(self, wait: float = 10.0) -> bool:
        """Launch Discord with remote debugging enabled.

        Handles snap, deb, and manual installs:
        - If Discord is already running with CDP, reuse it
        - If snap Discord is running without CDP, kills it and relaunches the
          binary directly with --remote-debugging-port
        - Otherwise finds and launches the Discord binary with CDP
        """
        # Check if Discord is already running with CDP
        if self._check_cdp_available():
            log.info("Discord already running with CDP on port %d", self.cdp_port)
            return True

        # Kill any existing Discord instances (snap auto-restarts without CDP)
        self._kill_existing_discord()

        # Find Discord binary
        discord_bin = self._find_discord_binary()
        if not discord_bin:
            log.error("Discord not found. Install Discord desktop for Linux.")
            log.error("Checked: %s", ", ".join(DISCORD_PATHS))
            return False

        # Build launch args — snap Discord needs --no-sandbox
        args = [discord_bin, f"--remote-debugging-port={self.cdp_port}"]
        if "snap" in discord_bin:
            args.extend(["--no-sandbox", "--disable-seccomp-filter-sandbox"])

        # Disable the update nag that makes Discord auto-quit
        self._set_skip_host_update()

        log.info("Launching Discord with CDP on port %d...", self.cdp_port)
        log.info("Binary: %s", discord_bin)
        try:
            self._discord_process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            log.info("Discord PID: %d. Waiting %.0fs for startup...",
                     self._discord_process.pid, wait)
            # Wait and poll for CDP to come up
            deadline = time.time() + wait
            while time.time() < deadline:
                time.sleep(1)
                if self._check_cdp_available():
                    log.info("CDP ready!")
                    return True
            return self._check_cdp_available()
        except Exception as e:
            log.error("Failed to launch Discord: %s", e)
            return False

    def _kill_existing_discord(self):
        """Kill running Discord instances so we can restart with CDP."""
        try:
            subprocess.run(["pkill", "-f", "discord/Discord"],
                          capture_output=True, timeout=5)
            time.sleep(2)
            # Make sure they're gone
            subprocess.run(["pkill", "-9", "-f", "discord/Discord"],
                          capture_output=True, timeout=5)
            time.sleep(1)
        except Exception:
            pass

    def _find_discord_binary(self) -> Optional[str]:
        """Find the Discord binary on the system."""
        for path in DISCORD_PATHS:
            if os.path.isfile(path):
                return path
            if "/" not in path and self._is_in_path(path):
                return path
        return None

    def _set_skip_host_update(self):
        """Set SKIP_HOST_UPDATE in Discord's settings.json to prevent auto-quit."""
        for data_dir in DISCORD_DATA_DIRS:
            settings_path = os.path.join(data_dir, "settings.json")
            if os.path.isfile(settings_path):
                try:
                    with open(settings_path, 'r') as f:
                        settings = json.load(f)
                    settings["SKIP_HOST_UPDATE"] = True
                    with open(settings_path, 'w') as f:
                        json.dump(settings, f, indent=2)
                    log.info("Set SKIP_HOST_UPDATE in %s", settings_path)
                except Exception:
                    pass

    def _check_cdp_available(self) -> bool:
        """Check if the CDP endpoint is responding."""
        try:
            resp = requests.get(f"http://127.0.0.1:{self.cdp_port}/json", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def _is_in_path(self, cmd: str) -> bool:
        """Check if a command is available in PATH."""
        if "/" in cmd:
            return False
        try:
            subprocess.run(["which", cmd], capture_output=True, check=True)
            return True
        except Exception:
            return False

    def connect_cdp(self) -> bool:
        """Connect to Discord's renderer via CDP."""
        return self.cdp.connect()

    def extract_token(self) -> Optional[str]:
        """Extract the user token from the live Discord session."""
        self._token = self.cdp.extract_token()
        if self._token:
            self.api = DiscordAPIClient(self._token)
            user = self.api.user_info
            if user:
                log.info("Authenticated as: %s#%s (%s)",
                        user.get("username", "?"),
                        user.get("discriminator", "?"),
                        user.get("id", "?"))
            return self._token
        return None

    def full_startup(self) -> bool:
        """Complete startup sequence: launch → connect → extract → verify."""
        log.info("=== Discord Controller — The Hacky Way ===")
        log.info("")

        # Step 1: Launch
        if not self.launch():
            log.error("Failed to launch Discord with CDP")
            return False

        # Step 2: Connect via CDP
        if not self.connect_cdp():
            log.error("Failed to connect to Discord via CDP")
            return False

        # Step 3: Extract token
        token = self.extract_token()
        if not token:
            log.error("Failed to extract token")
            return False

        log.info("")
        log.info("=== Ready to rock. No bot needed. ===")
        return True

    def scan_threads(self, channel_id: str, min_inactive_days: int = 30) -> dict:
        """Scan a channel for stale threads using the extracted token."""
        if not self.api:
            raise RuntimeError("Not authenticated. Call full_startup() first.")

        from utils import is_thread_stale, categorize_thread, age_bucket, get_thread_last_activity

        log.info("Scanning channel %s for threads...", channel_id)
        all_threads = []

        # Active
        active = self.api.list_active_threads(channel_id)
        log.info("Active threads: %d", len(active))
        for t in active:
            t["_source"] = "active"
        all_threads.extend(active)

        # Public archived
        pub = self.api.list_public_archived_threads(channel_id)
        log.info("Public archived: %d", len(pub))
        for t in pub:
            t["_source"] = "public_archived"
        all_threads.extend(pub)

        # Private archived
        priv = self.api.list_private_archived_threads(channel_id)
        log.info("Private archived: %d", len(priv))
        for t in priv:
            t["_source"] = "private_archived"
        all_threads.extend(priv)

        # Deduplicate
        seen = set()
        unique = []
        for t in all_threads:
            if t["id"] not in seen:
                seen.add(t["id"])
                unique.append(t)
        all_threads = unique

        # Analyze
        stale = []
        now = datetime.now(timezone.utc)
        for thread in all_threads:
            last_activity = get_thread_last_activity(thread)
            days_inactive = (now - last_activity).days
            metadata = thread.get("thread_metadata", {})

            enriched = {
                "id": thread["id"],
                "name": thread.get("name", "Untitled"),
                "last_activity": last_activity.isoformat(),
                "days_inactive": days_inactive,
                "message_count": thread.get("message_count", 0),
                "is_archived": metadata.get("archived", False),
                "is_locked": metadata.get("locked", False),
                "source": thread.get("_source", "unknown"),
                "parent_id": thread.get("parent_id"),
                "owner_id": thread.get("owner_id"),
            }
            enriched["category"] = categorize_thread(thread)

            if days_inactive >= min_inactive_days:
                enriched["age_bucket"] = age_bucket(days_inactive)
                stale.append(enriched)

        result = {
            "scan_metadata": {
                "channel_id": channel_id,
                "scan_timestamp": now.isoformat(),
                "min_inactive_days": min_inactive_days,
                "total_threads_scanned": len(all_threads),
                "total_stale": len(stale),
            },
            "all_threads": all_threads,
            "stale_threads": stale,
        }
        log.info("Scan complete: %d total, %d stale", len(all_threads), len(stale))
        return result

    def lock_and_archive_threads(self, thread_ids: list,
                                  dry_run: bool = True,
                                  batch_delay: float = 1.0,
                                  exclude_ids: list = None) -> dict:
        """Lock and archive stale threads. Always dry-run first."""
        if not self.api:
            raise RuntimeError("Not authenticated. Call full_startup() first.")

        exclude_ids = set(exclude_ids or [])
        results = {"locked": [], "archived": [], "skipped": [], "failed": []}

        for tid in thread_ids:
            if tid in exclude_ids:
                results["skipped"].append({"id": tid, "reason": "excluded"})
                continue

            if dry_run:
                log.info("[DRY RUN] Would lock & archive thread %s", tid)
                results["locked"].append({"id": tid, "dry_run": True})
                results["archived"].append({"id": tid, "dry_run": True})
            else:
                lock_ok, archive_ok = self.api.lock_and_archive(tid)
                if lock_ok:
                    results["locked"].append({"id": tid})
                else:
                    results["failed"].append({"id": tid, "step": "lock"})
                if archive_ok:
                    results["archived"].append({"id": tid})
                else:
                    results["failed"].append({"id": tid, "step": "archive"})

            time.sleep(batch_delay)

        return results

    def cleanup(self):
        """Close CDP connection. Does NOT kill Discord."""
        self.cdp.close()
        log.info("CDP connection closed. Discord is still running.")


# ---------------------------------------------------------------------------
# Snowflake / Date Helpers (self-contained, no utils dependency needed)
# ---------------------------------------------------------------------------

def snowflake_to_datetime(snowflake: int) -> datetime:
    ts_ms = (snowflake >> 22) + DISCORD_EPOCH_MS
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Discord Controller — The Hacky Way (no bot token needed)")
    parser.add_argument("--cdp-port", type=int, default=CDP_PORT)
    parser.add_argument("--action", choices=["scan", "lock", "full"], default="full",
                       help="Action to perform (default: full startup)")
    parser.add_argument("--channel-id", help="Channel ID for scanning")
    parser.add_argument("--min-inactive-days", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--confirm", action="store_true", help="Actually execute (no dry run)")
    parser.add_argument("--output", default="stale_threads.json")

    args = parser.parse_args()

    ctrl = DiscordController(cdp_port=args.cdp_port)

    if not ctrl.full_startup():
        sys.exit(1)

    if args.action in ("scan", "full") and args.channel_id:
        result = ctrl.scan_threads(args.channel_id, args.min_inactive_days)
        from utils import save_json
        save_json(result, args.output)

        meta = result["scan_metadata"]
        print(f"\n{'='*60}")
        print(f"HACKY SCAN — Channel {args.channel_id}")
        print(f"{'='*60}")
        print(f"Total scanned: {meta['total_threads_scanned']}")
        print(f"Stale ({args.min_inactive_days}+ days): {meta['total_stale']}")
        print(f"Results: {args.output}")

    if args.action == "lock" and args.channel_id:
        result = ctrl.scan_threads(args.channel_id, args.min_inactive_days)
        thread_ids = [t["id"] for t in result["stale_threads"]]
        dry_run = not args.confirm
        lock_result = ctrl.lock_and_archive_threads(
            thread_ids, dry_run=dry_run)
        print(f"\nLock results: {json.dumps(lock_result, indent=2)}")

    ctrl.cleanup()


if __name__ == "__main__":
    main()
