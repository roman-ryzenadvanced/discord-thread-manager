#!/usr/bin/env python3
"""
Scan a Discord channel for stale (inactive) threads.

Discovers ALL threads in a channel — active, public-archived, and private-archived —
then filters by inactivity period and outputs a structured JSON report.

Usage:
    python scan_threads.py --channel-id 123456789 --min-inactive-days 30
    python scan_threads.py --channel-id 123456789 --min-inactive-days 60 --output stale.json
"""

import argparse
import sys
import time
import logging
from datetime import datetime, timezone, timedelta

from utils import (
    DiscordClient,
    is_thread_stale,
    categorize_thread,
    age_bucket,
    get_thread_last_activity,
    save_json,
    load_json,
    log,
)

log.setLevel(logging.INFO)


def scan_channel(client: DiscordClient, channel_id: str, min_inactive_days: int) -> dict:
    """Scan a channel for all threads and identify stale ones.

    Returns a dict with:
      - scan_metadata: info about the scan itself
      - all_threads: list of all discovered threads
      - stale_threads: list of threads meeting the inactivity threshold
      - summary: aggregate statistics
    """
    log.info("Scanning channel %s for threads (min inactive: %d days)", channel_id, min_inactive_days)

    # --- Phase 1: Collect all threads ---
    all_threads = []

    # Active threads
    log.info("Fetching active threads...")
    active = client.list_active_threads(channel_id)
    log.info("Found %d active threads", len(active))
    for t in active:
        t["_source"] = "active"
    all_threads.extend(active)

    # Public archived threads
    log.info("Fetching public archived threads...")
    public_archived = client.list_public_archived_threads(channel_id)
    log.info("Found %d public archived threads", len(public_archived))
    for t in public_archived:
        t["_source"] = "public_archived"
    all_threads.extend(public_archived)

    # Private archived threads
    log.info("Fetching private archived threads...")
    private_archived = client.list_private_archived_threads(channel_id)
    log.info("Found %d private archived threads", len(private_archived))
    for t in private_archived:
        t["_source"] = "private_archived"
    all_threads.extend(private_archived)

    # Deduplicate by thread ID (a thread might appear in multiple lists)
    seen_ids = set()
    unique_threads = []
    for t in all_threads:
        if t["id"] not in seen_ids:
            seen_ids.add(t["id"])
            unique_threads.append(t)
    all_threads = unique_threads

    log.info("Total unique threads discovered: %d", len(all_threads))

    # --- Phase 2: Analyze each thread ---
    stale_threads = []
    now = datetime.now(timezone.utc)

    for i, thread in enumerate(all_threads):
        thread_id = thread["id"]
        thread_name = thread.get("name", "Untitled")

        # Fetch a few messages for categorization and better activity detection
        # (optional but improves accuracy; skip if rate-limited)
        messages = None
        if i % 5 == 0:  # Only fetch messages for every 5th thread to save API calls
            try:
                messages = client.get_thread_messages(thread_id, limit=3)
                time.sleep(0.3)  # Rate limit courtesy
            except Exception:
                messages = None

        # Determine last activity
        last_activity = get_thread_last_activity(thread, messages)
        days_inactive = (now - last_activity).days

        # Determine message count
        message_count = thread.get("message_count", 0)

        # Check thread state
        metadata = thread.get("thread_metadata", {})
        is_archived = metadata.get("archived", False)
        is_locked = metadata.get("locked", False)
        auto_archive_duration = metadata.get("auto_archive_duration", 0)

        # Build enriched thread record
        enriched = {
            "id": thread_id,
            "name": thread_name,
            "created_at": thread.get("id"),  # snowflake encodes creation time
            "last_activity": last_activity.isoformat(),
            "days_inactive": days_inactive,
            "message_count": message_count,
            "is_archived": is_archived,
            "is_locked": is_locked,
            "auto_archive_duration": auto_archive_duration,
            "source": thread.get("_source", "unknown"),
            "parent_id": thread.get("parent_id"),
            "owner_id": thread.get("owner_id"),
        }

        # Categorize
        enriched["category"] = categorize_thread(thread, messages)

        # Check staleness
        if days_inactive >= min_inactive_days:
            enriched["age_bucket"] = age_bucket(days_inactive)
            stale_threads.append(enriched)

    # --- Phase 3: Build summary ---
    age_distribution = {}
    for t in stale_threads:
        bucket = t.get("age_bucket", "unknown")
        age_distribution[bucket] = age_distribution.get(bucket, 0) + 1

    category_distribution = {}
    for t in stale_threads:
        cat = t.get("category", "unknown")
        category_distribution[cat] = category_distribution.get(cat, 0) + 1

    never_responded = [t for t in stale_threads if t["message_count"] <= 1]

    oldest = max(stale_threads, key=lambda t: t["days_inactive"]) if stale_threads else None

    summary = {
        "channel_id": channel_id,
        "scan_timestamp": now.isoformat(),
        "min_inactive_days": min_inactive_days,
        "total_threads_scanned": len(all_threads),
        "total_stale": len(stale_threads),
        "never_responded": len(never_responded),
        "age_distribution": age_distribution,
        "category_distribution": category_distribution,
        "oldest_thread": {
            "id": oldest["id"],
            "name": oldest["name"],
            "days_inactive": oldest["days_inactive"],
        } if oldest else None,
    }

    result = {
        "scan_metadata": summary,
        "all_threads": all_threads,
        "stale_threads": stale_threads,
    }

    log.info("Scan complete: %d total, %d stale, %d never responded",
             len(all_threads), len(stale_threads), len(never_responded))

    return result


def main():
    parser = argparse.ArgumentParser(description="Scan Discord channel for stale threads")
    parser.add_argument("--channel-id", required=True, help="Discord channel ID to scan")
    parser.add_argument("--min-inactive-days", type=int, default=30,
                        help="Minimum days of inactivity to flag as stale (default: 30)")
    parser.add_argument("--output", default="stale_threads.json",
                        help="Output path for JSON results (default: stale_threads.json)")

    args = parser.parse_args()

    client = DiscordClient()
    result = scan_channel(client, args.channel_id, args.min_inactive_days)
    save_json(result, args.output)

    # Print a quick summary to stdout
    meta = result["scan_metadata"]
    print(f"\n{'='*60}")
    print(f"SCAN SUMMARY — Channel {args.channel_id}")
    print(f"{'='*60}")
    print(f"Total threads scanned:   {meta['total_threads_scanned']}")
    print(f"Stale threads ({args.min_inactive_days}+ days): {meta['total_stale']}")
    print(f"Never responded (0-1 msgs): {meta['never_responded']}")
    print(f"\nAge Breakdown:")
    for bucket, count in sorted(meta["age_distribution"].items()):
        print(f"  {bucket}: {count}")
    print(f"\nCategory Breakdown:")
    for cat, count in sorted(meta["category_distribution"].items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    if meta["oldest_thread"]:
        print(f"\nOldest stale thread: {meta['oldest_thread']['name']} ({meta['oldest_thread']['days_inactive']} days)")
    print(f"\nFull results saved to: {args.output}")


if __name__ == "__main__":
    main()
