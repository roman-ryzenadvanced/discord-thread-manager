#!/usr/bin/env python3
"""
Generate a report from stale thread scan data.

Works with output from scan_threads.py (the hacky version).
Supports markdown and JSON formats.

Usage:
    python generate_report.py --input stale_threads.json
    python generate_report.py --input stale_threads.json --categorize --output report.md
"""

import argparse
import json
from datetime import datetime
from utils import load_json

def generate_markdown_report(scan_data: dict, categorize: bool = True) -> str:
    meta = scan_data["scan_metadata"]
    stale = scan_data.get("stale_threads", [])
    lines = []

    lines.append(f"# 🕵️ Stale Threads Report — The Hacky Way")
    lines.append(f"")
    lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"Auth: User token (extracted via CDP — no bot needed)")
    lines.append(f"")

    lines.append(f"## Key Findings")
    lines.append(f"")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total scanned | {meta.get('total_threads_scanned', 0)} |")
    lines.append(f"| Stale ({meta.get('min_inactive_days', '?')}+ days) | {meta.get('total_stale', 0)} |")
    lines.append(f"")

    # Age
    age_dist = {}
    for t in stale:
        b = t.get("age_bucket", "unknown")
        age_dist[b] = age_dist.get(b, 0) + 1
    if age_dist:
        lines.append(f"## Age Breakdown")
        lines.append(f"")
        lines.append(f"| Range | Count |")
        lines.append(f"|-------|-------|")
        for bucket in ["30-60 days", "60-90 days", "90-180 days", "180+ days"]:
            if bucket in age_dist:
                lines.append(f"| {bucket} | {age_dist[bucket]} |")
        lines.append(f"")

    # Category
    cat_dist = {}
    for t in stale:
        c = t.get("category", "unknown")
        cat_dist[c] = cat_dist.get(c, 0) + 1
    if categorize and cat_dist:
        lines.append(f"## Issue Categories")
        lines.append(f"")
        lines.append(f"| Category | Count |")
        lines.append(f"|----------|-------|")
        for cat, count in sorted(cat_dist.items(), key=lambda x: -x[1]):
            lines.append(f"| {cat} | {count} |")
        lines.append(f"")

    # Thread list
    lines.append(f"## Stale Thread Details")
    lines.append(f"")
    for i, thread in enumerate(sorted(stale, key=lambda t: -t.get("days_inactive", 0)), 1):
        lines.append(f"### {i}. {thread.get('name', 'Untitled')}")
        lines.append(f"")
        lines.append(f"- **ID**: `{thread['id']}`")
        lines.append(f"- **Inactive**: {thread.get('days_inactive', '?')} days")
        lines.append(f"- **Messages**: {thread.get('message_count', 0)}")
        lines.append(f"- **Category**: {thread.get('category', 'N/A')}")
        lines.append(f"- **Archived**: {'✓' if thread.get('is_archived') else '✗'}")
        lines.append(f"- **Locked**: {'✓' if thread.get('is_locked') else '✗'}")
        lines.append(f"")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate report from hacky scan data")
    parser.add_argument("--input", required=True)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", default=None)
    parser.add_argument("--categorize", action="store_true")

    args = parser.parse_args()
    data = load_json(args.input)

    if args.format == "markdown":
        report = generate_markdown_report(data, categorize=args.categorize)
        out = args.output or "stale_report.md"
        with open(out, "w") as f:
            f.write(report)
    else:
        report = {"summary": data["scan_metadata"], "stale_threads": data["stale_threads"]}
        out = args.output or "stale_report.json"
        with open(out, "w") as f:
            json.dump(report, f, indent=2, default=str)

    print(f"Report saved to: {out}")

if __name__ == "__main__":
    main()
