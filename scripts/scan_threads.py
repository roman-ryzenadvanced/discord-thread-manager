#!/usr/bin/env python3
"""
Scan Discord channel for stale threads — The Hacky Way.

No bot token needed. Launches Discord with CDP, extracts your user token
from the running session, then scans all threads via the Discord REST API.

Usage:
    python scan_threads.py --channel-id 123456789
    python scan_threads.py --channel-id 123456789 --min-inactive-days 60 --output stale.json
"""

import argparse
import sys
from discord_controller import DiscordController
from utils import save_json

def main():
    parser = argparse.ArgumentParser(
        description="Scan Discord threads — The Hacky Way (no bot token)")
    parser.add_argument("--channel-id", required=True)
    parser.add_argument("--min-inactive-days", type=int, default=30)
    parser.add_argument("--output", default="stale_threads.json")
    parser.add_argument("--cdp-port", type=int, default=9222)

    args = parser.parse_args()

    ctrl = DiscordController(cdp_port=args.cdp_port)
    if not ctrl.full_startup():
        print("Failed to start. Is Discord installed?")
        sys.exit(1)

    result = ctrl.scan_threads(args.channel_id, args.min_inactive_days)
    save_json(result, args.output)
    ctrl.cleanup()

    meta = result["scan_metadata"]
    print(f"\n{'='*60}")
    print(f"  HACKY SCAN RESULTS — Channel {args.channel_id}")
    print(f"{'='*60}")
    print(f"  Token extracted: ✓ (no bot needed)")
    print(f"  Total scanned:   {meta['total_threads_scanned']}")
    print(f"  Stale threads:   {meta['total_stale']}")
    print(f"  Saved to:        {args.output}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
