#!/usr/bin/env python3
"""
Generate a human-readable report from stale thread scan data.

Supports markdown and JSON output formats. Can auto-categorize threads
by issue type using keyword matching.

Usage:
    python generate_report.py --input stale_threads.json --format markdown
    python generate_report.py --input stale_threads.json --format markdown --categorize --output report.md
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from utils import load_json, log


def generate_markdown_report(scan_data: dict, categorize: bool = True) -> str:
    """Generate a markdown report from scan data."""
    meta = scan_data["scan_metadata"]
    stale_threads = scan_data["stale_threads"]

    lines = []

    # Header
    lines.append(f"# Stale Threads Report — Channel {meta['channel_id']}")
    lines.append(f"")
    lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"")

    # Key Findings
    lines.append(f"## Key Findings")
    lines.append(f"")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total threads scanned | {meta['total_threads_scanned']} |")
    lines.append(f"| Total stale ({meta['min_inactive_days']}+ days inactive) | {meta['total_stale']} |")
    lines.append(f"| Never responded (0-1 msgs) | {meta['never_responded']} |")

    locked_count = sum(1 for t in stale_threads if t.get("is_locked"))
    if locked_count:
        lines.append(f"| Already locked | {locked_count} |")
    lines.append(f"")

    # Age Breakdown
    lines.append(f"## Age Breakdown")
    lines.append(f"")
    lines.append(f"| Range | Count |")
    lines.append(f"|-------|-------|")
    for bucket in ["30-60 days", "60-90 days", "90-180 days", "180+ days"]:
        count = meta.get("age_distribution", {}).get(bucket, 0)
        if count:
            lines.append(f"| {bucket} | {count} |")
    lines.append(f"")

    # Category Breakdown
    if categorize and meta.get("category_distribution"):
        lines.append(f"## Issue Categories")
        lines.append(f"")
        lines.append(f"| Category | Count |")
        lines.append(f"|----------|-------|")
        for cat, count in sorted(meta["category_distribution"].items(), key=lambda x: -x[1]):
            lines.append(f"| {cat} | {count} |")
        lines.append(f"")

    # Thread Details
    lines.append(f"## Stale Thread Details")
    lines.append(f"")

    # Sort by days inactive (oldest first)
    sorted_threads = sorted(stale_threads, key=lambda t: -t.get("days_inactive", 0))

    for i, thread in enumerate(sorted_threads, 1):
        lines.append(f"### {i}. {thread.get('name', 'Untitled')}")
        lines.append(f"")
        lines.append(f"- **Thread ID**: {thread['id']}")
        lines.append(f"- **Days Inactive**: {thread.get('days_inactive', 'N/A')}")
        lines.append(f"- **Age Bucket**: {thread.get('age_bucket', 'N/A')}")
        lines.append(f"- **Message Count**: {thread.get('message_count', 'N/A')}")
        lines.append(f"- **Category**: {thread.get('category', 'N/A')}")
        lines.append(f"- **Archived**: {'Yes' if thread.get('is_archived') else 'No'}")
        lines.append(f"- **Locked**: {'Yes' if thread.get('is_locked') else 'No'}")
        lines.append(f"- **Source**: {thread.get('source', 'N/A')}")
        if thread.get("owner_id"):
            lines.append(f"- **Owner ID**: {thread['owner_id']}")
        if thread.get("parent_id"):
            lines.append(f"- **Parent ID**: {thread['parent_id']}")
        lines.append(f"")

    return "\n".join(lines)


def generate_json_report(scan_data: dict) -> dict:
    """Generate a structured JSON report from scan data."""
    return {
        "report_metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "channel_id": scan_data["scan_metadata"]["channel_id"],
        },
        "summary": scan_data["scan_metadata"],
        "stale_threads": scan_data["stale_threads"],
    }


def main():
    parser = argparse.ArgumentParser(description="Generate report from stale thread scan data")
    parser.add_argument("--input", required=True, help="Path to scan JSON file")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown",
                        help="Output format (default: markdown)")
    parser.add_argument("--output", default=None,
                        help="Output file path (default: stale_report.md or stale_report.json)")
    parser.add_argument("--categorize", action="store_true",
                        help="Include auto-categorization by issue type")

    args = parser.parse_args()

    scan_data = load_json(args.input)

    if args.format == "markdown":
        report = generate_markdown_report(scan_data, categorize=args.categorize)
        default_output = "stale_report.md"
    else:
        report = generate_json_report(scan_data)
        default_output = "stale_report.json"

    output_path = args.output or default_output

    if args.format == "markdown":
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
    else:
        from utils import save_json
        save_json(report, output_path)

    print(f"Report saved to: {output_path}")


if __name__ == "__main__":
    main()
