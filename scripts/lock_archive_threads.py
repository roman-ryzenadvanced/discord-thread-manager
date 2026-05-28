#!/usr/bin/env python3
"""
Lock & archive stale Discord threads — The Hacky Way.

Uses the extracted user token (via CDP) to lock and archive threads.
ALWAYS dry-run first. Get explicit user confirmation before --confirm.

Usage:
    python lock_archive_threads.py --input stale_threads.json --dry-run
    python lock_archive_threads.py --input stale_threads.json --confirm
"""

import argparse
import json
import sys
from discord_controller import DiscordController
from utils import load_json

def main():
    parser = argparse.ArgumentParser(
        description="Lock & archive threads — The Hacky Way")
    parser.add_argument("--input", required=True, help="Scan JSON from scan_threads.py")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="Show what would happen (default)")
    parser.add_argument("--confirm", action="store_true",
                       help="⚠️ Actually execute the operations")
    parser.add_argument("--exclude-ids", help="Comma-separated thread IDs to skip")
    parser.add_argument("--batch-delay", type=float, default=1.0,
                       help="Seconds between API calls (default: 1.0)")
    parser.add_argument("--cdp-port", type=int, default=9222)

    args = parser.parse_args()
    dry_run = not args.confirm
    exclude = args.exclude_ids.split(",") if args.exclude_ids else []

    if args.confirm:
        print("⚠️  WARNING: This will actually lock and archive threads!")
        confirm = input("Type 'yes' to confirm: ").strip().lower()
        if confirm not in ("yes", "confirm", "do it"):
            print("Aborted.")
            sys.exit(0)

    # Load scan data
    scan_data = load_json(args.input)
    thread_ids = [t["id"] for t in scan_data.get("stale_threads", [])]
    if not thread_ids:
        print("No stale threads found in input.")
        sys.exit(0)

    # Startup
    ctrl = DiscordController(cdp_port=args.cdp_port)
    if not ctrl.full_startup():
        print("Failed to start.")
        sys.exit(1)

    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\n{'='*60}")
    print(f"  {mode} — Processing {len(thread_ids)} threads")
    print(f"{'='*60}")

    result = ctrl.lock_and_archive_threads(
        thread_ids,
        dry_run=dry_run,
        batch_delay=args.batch_delay,
        exclude_ids=exclude,
    )

    ctrl.cleanup()

    # Report
    print(f"\n{'='*60}")
    print(f"  RESULTS ({mode})")
    print(f"{'='*60}")
    print(f"  Processed: {len(thread_ids)}")
    print(f"  Locked:    {len(result['locked'])}")
    print(f"  Archived:  {len(result['archived'])}")
    print(f"  Skipped:   {len(result['skipped'])}")
    print(f"  Failed:    {len(result['failed'])}")

    if result["failed"]:
        print(f"\n  ⚠️ Failed threads:")
        for f in result["failed"]:
            print(f"    - {f['id']} (step: {f['step']})")

    # Save results
    out_file = args.input.replace(".json", "_results.json")
    with open(out_file, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    print(f"\n  Results saved to: {out_file}")

if __name__ == "__main__":
    main()
