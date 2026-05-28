#!/usr/bin/env python3
"""
Lock and archive stale Discord threads in bulk.

Reads the scan JSON output and applies lock + archive operations to each
stale thread. Supports dry-run mode, exclusion lists, and rate-limit-safe
batching.

IMPORTANT: Always run with --dry-run first and get user confirmation
before using --confirm.

Usage:
    # Dry run (show what would happen)
    python lock_archive_threads.py --input stale_threads.json --dry-run

    # Confirm (actually lock & archive)
    python lock_archive_threads.py --input stale_threads.json --confirm

    # Exclude specific threads
    python lock_archive_threads.py --input stale_threads.json --confirm --exclude-ids 111,222,333
"""

import argparse
import sys
import time
import logging
from datetime import datetime, timezone

from utils import (
    DiscordClient,
    load_json,
    save_json,
    log,
)

log.setLevel(logging.INFO)


def process_threads(
    client: DiscordClient,
    threads: list[dict],
    dry_run: bool = True,
    exclude_ids: set[str] | None = None,
    batch_delay: float = 1.0,
) -> dict:
    """Lock and archive each thread in the list.

    Returns a summary dict with success/failure counts and details.
    """
    exclude_ids = exclude_ids or set()
    results = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "total_to_process": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "already_locked": 0,
        "already_archived": 0,
        "details": [],
    }

    # Filter out excluded threads and already-processed ones
    to_process = []
    for t in threads:
        tid = str(t["id"])
        if tid in exclude_ids:
            results["skipped"] += 1
            results["details"].append({
                "thread_id": tid,
                "name": t.get("name", ""),
                "status": "skipped_excluded",
            })
            continue
        to_process.append(t)

    results["total_to_process"] = len(to_process)

    if dry_run:
        log.info("DRY RUN — would process %d threads", len(to_process))
        for t in to_process:
            results["details"].append({
                "thread_id": t["id"],
                "name": t.get("name", ""),
                "days_inactive": t.get("days_inactive", 0),
                "category": t.get("category", ""),
                "status": "would_lock_archive",
            })
        results["success"] = len(to_process)
        return results

    # --- Live execution ---
    log.info("Processing %d threads...", len(to_process))

    for i, thread in enumerate(to_process, 1):
        tid = str(thread["id"])
        name = thread.get("name", "Untitled")

        log.info("[%d/%d] Processing: %s (%s)", i, len(to_process), name, tid)

        try:
            # Lock first, then archive — order matters!
            lock_ok, archive_ok = client.lock_and_archive_thread(tid)

            status = "success"
            if lock_ok and archive_ok:
                results["success"] += 1
            elif not lock_ok and archive_ok:
                status = "archive_only"
                results["success"] += 1
                log.warning("Thread %s: archived but could not lock (permission issue?)", tid)
            elif lock_ok and not archive_ok:
                status = "lock_only"
                results["success"] += 1
                log.warning("Thread %s: locked but could not archive", tid)
            else:
                status = "failed"
                results["failed"] += 1
                log.error("Thread %s: both lock and archive failed", tid)

            results["details"].append({
                "thread_id": tid,
                "name": name,
                "days_inactive": thread.get("days_inactive", 0),
                "lock_success": lock_ok,
                "archive_success": archive_ok,
                "status": status,
            })

        except Exception as e:
            results["failed"] += 1
            results["details"].append({
                "thread_id": tid,
                "name": name,
                "status": "error",
                "error": str(e),
            })
            log.error("Thread %s: exception — %s", tid, e)

        # Rate-limit-safe delay between threads
        if i < len(to_process):
            time.sleep(batch_delay)

    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    return results


def retry_failed(client: DiscordClient, results: dict, batch_delay: float = 1.0) -> dict:
    """Retry any threads that failed in a previous run.

    Reads the results dict and retries entries with status 'failed' or 'error'.
    """
    failed_threads = [
        d for d in results["details"]
        if d.get("status") in ("failed", "error")
    ]

    if not failed_threads:
        log.info("No failed threads to retry.")
        return results

    log.info("Retrying %d failed threads...", len(failed_threads))

    for detail in failed_threads:
        tid = detail["thread_id"]
        try:
            lock_ok, archive_ok = client.lock_and_archive_thread(tid)
            if lock_ok or archive_ok:
                detail["status"] = "success_on_retry"
                detail["lock_success"] = lock_ok
                detail["archive_success"] = archive_ok
                results["failed"] -= 1
                results["success"] += 1
                log.info("Retry success: %s", tid)
            else:
                log.warning("Retry still failed: %s", tid)
            time.sleep(batch_delay)
        except Exception as e:
            detail["status"] = "retry_error"
            detail["error"] = str(e)
            log.error("Retry exception for %s: %s", tid, e)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Lock and archive stale Discord threads in bulk"
    )
    parser.add_argument("--input", required=True,
                        help="Path to scan JSON file (from scan_threads.py)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without making changes")
    parser.add_argument("--confirm", action="store_true",
                        help="Actually execute lock & archive operations")
    parser.add_argument("--exclude-ids", default="",
                        help="Comma-separated thread IDs to exclude")
    parser.add_argument("--batch-delay", type=float, default=1.0,
                        help="Seconds between API calls (default: 1.0)")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Retry threads that failed in a previous run (reads from --results-file)")
    parser.add_argument("--results-file", default=None,
                        help="Path to previous results JSON for retry (default: auto-detect)")

    args = parser.parse_args()

    if not args.dry_run and not args.confirm:
        print("ERROR: Specify either --dry-run or --confirm.")
        print("  --dry-run   Show what would happen without making changes")
        print("  --confirm   Actually lock & archive the threads")
        sys.exit(1)

    # Load scan data
    scan_data = load_json(args.input)
    stale_threads = scan_data.get("stale_threads", [])

    if not stale_threads:
        print("No stale threads found in the input file.")
        sys.exit(0)

    # Parse exclude IDs
    exclude_ids = set()
    if args.exclude_ids:
        exclude_ids = {x.strip() for x in args.exclude_ids.split(",") if x.strip()}

    client = DiscordClient()

    # Handle retry mode
    if args.retry_failed:
        results_file = args.results_file
        if not results_file:
            # Try to find the most recent results file
            import glob
            candidates = sorted(glob.glob("lock_results_*.json"), reverse=True)
            if not candidates:
                print("No previous results file found. Run without --retry-failed first.")
                sys.exit(1)
            results_file = candidates[0]

        previous_results = load_json(results_file)
        results = retry_failed(client, previous_results, args.batch_delay)
    else:
        results = process_threads(
            client,
            stale_threads,
            dry_run=args.dry_run,
            exclude_ids=exclude_ids,
            batch_delay=args.batch_delay,
        )

    # Save results
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_path = f"lock_results_{timestamp}.json"
    save_json(results, results_path)

    # Print summary
    print(f"\n{'='*60}")
    if args.dry_run:
        print(f"DRY RUN SUMMARY")
    else:
        print(f"EXECUTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total processed: {results['total_to_process']}")
    print(f"Successful:       {results['success']}")
    print(f"Failed:           {results['failed']}")
    print(f"Skipped:          {results['skipped']}")
    print(f"\nResults saved to: {results_path}")

    if results["failed"] > 0:
        print(f"\n⚠ {results['failed']} threads failed. Retry with:")
        print(f"  python lock_archive_threads.py --input {args.input} --confirm --retry-failed --results-file {results_path}")


if __name__ == "__main__":
    main()
