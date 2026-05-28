---
name: discord-thread-manager
description: >
  Manage Discord server threads at scale — scan for stale/inactive threads, generate
  detailed reports with categorization and age breakdowns, and bulk lock & archive
  threads that have been inactive for a configurable period. Use this skill whenever
  the user mentions Discord thread management, stale threads, channel cleanup, thread
  moderation, bulk archiving Discord threads, Discord server maintenance, or wants to
  audit and clean up thread clutter. Also triggers on requests about Discord API
  thread operations, Discord moderation automation, or any task involving programmatically
  managing Discord threads.
---

# Discord Thread Manager

This skill enables an AI agent to manage Discord threads programmatically via the
Discord REST API. It covers the full lifecycle: **scan → report → act**.

## Why this skill exists

Discord servers with high volumes of support or discussion threads accumulate stale,
unanswered, and auto-archived threads over time. Manually reviewing and closing them
is impractical at scale. This skill automates the entire process while being safe,
auditable, and respectful of Discord's rate limits.

## Prerequisites

- A Discord token (bot token or user account token) with appropriate permissions
- The `MANAGE_THREADS` permission is required to lock threads
- The `READ_MESSAGE_HISTORY` permission is required to scan thread content
- Python 3.9+ with `requests` installed

## Environment Setup

Set the following environment variables before using any script:

```bash
export DISCORD_TOKEN="your-token-here"       # Bot token or user account token
export DISCORD_CHANNEL_ID="123456789"         # Target channel ID
```

Or copy `.env.example` to `.env` and fill in your values. All scripts read from
`.env` automatically.

## Core Workflow

The workflow has three phases. Always execute them in order: scan first, then report,
then act. Never lock or archive threads without first generating a report the user
can review.

### Phase 1: Scan

Use `scripts/scan_threads.py` to discover all threads in a channel, including both
active and archived ones.

```bash
python scripts/scan_threads.py --channel-id 123456789 --min-inactive-days 30
```

Key parameters:
- `--channel-id` (required): The Discord channel ID to scan
- `--min-inactive-days` (default: 30): Minimum days of inactivity to flag as stale
- `--output` (default: `stale_threads.json`): Path for the JSON output

The scanner handles Discord API quirks automatically:
- Fetches both active and archived (public + private) threads
- Correctly paginates using `before` cursors (see `references/discord_api.md`)
- Handles the `+00:00` vs `Z` timezone issue in Discord timestamps
- Respects rate limits with automatic retry on 429 responses

Output is a JSON file with the full thread data, including:
- Thread ID, name, creation date, last activity
- Message count, whether it was ever responded to
- Whether it's locked, archived, or auto-archived

### Phase 2: Report

Use `scripts/generate_report.py` to produce a human-readable report from the scan data.

```bash
python scripts/generate_report.py --input stale_threads.json --format markdown
```

Key parameters:
- `--input` (required): Path to the JSON file from the scan phase
- `--format` (default: `markdown`): Output format — `markdown` or `json`
- `--output` (default: `stale_report.md`): Path for the report output
- `--categorize` (flag): Attempt to categorize threads by issue type using keyword matching

The report includes:
- **Summary metrics**: total scanned, total stale, never-responded count
- **Age breakdown**: threads bucketed by 30-60, 60-90, 90-180, 180+ days
- **Issue categories**: auto-categorized by keywords (subscription, billing, bug, API, performance, etc.)
- **Thread list**: full details for each stale thread

Always present the report to the user and get explicit confirmation before proceeding
to Phase 3. The user may want to exclude certain threads or adjust the criteria.

### Phase 3: Act (Lock & Archive)

Use `scripts/lock_archive_threads.py` to lock and archive the stale threads.

```bash
python scripts/lock_archive_threads.py --input stale_threads.json --dry-run
python scripts/lock_archive_threads.py --input stale_threads.json --confirm
```

Key parameters:
- `--input` (required): Path to the JSON file from the scan phase
- `--dry-run` (flag): Show what would happen without actually doing it
- `--confirm` (flag): Actually execute the lock & archive operations
- `--exclude-ids` (optional): Comma-separated list of thread IDs to skip
- `--batch-delay` (default: 1.0): Seconds between API calls to respect rate limits

**Safety requirements:**
1. ALWAYS run with `--dry-run` first and show the user what will happen
2. Get explicit user confirmation (user must say "yes", "confirm", or "do it")
3. Never run `--confirm` without the user's explicit go-ahead
4. The script processes threads in batches and logs every action
5. Failed operations are retried once; persistent failures are logged and reported

**Important API quirks to know:**
- Lock must be set BEFORE archiving for reliable behavior
- The `locked` field appears inside `thread_metadata.locked`, not at the top level
- Already-archived threads still need the lock operation applied separately
- User account tokens may show `locked: None` at top level even when successfully locked — always check `thread_metadata.locked`
- See `references/discord_api.md` for full details on these quirks

## Scripts Reference

| Script | Purpose | Key Flags |
|--------|---------|-----------|
| `scan_threads.py` | Discover and filter threads | `--channel-id`, `--min-inactive-days`, `--output` |
| `generate_report.py` | Produce reports from scan data | `--input`, `--format`, `--categorize` |
| `lock_archive_threads.py` | Lock & archive stale threads | `--input`, `--dry-run`, `--confirm`, `--exclude-ids` |
| `utils.py` | Shared API helpers (not run directly) | — |

## Common Patterns

### Quick scan and report
```bash
python scripts/scan_threads.py --channel-id 123456789 --min-inactive-days 30
python scripts/generate_report.py --input stale_threads.json --categorize
```

### Full cleanup with review
```bash
# Step 1: Scan
python scripts/scan_threads.py --channel-id 123456789 --min-inactive-days 30 --output my_scan.json

# Step 2: Report (review this before continuing!)
python scripts/generate_report.py --input my_scan.json --categorize --output my_report.md

# Step 3: Dry run (see what would happen)
python scripts/lock_archive_threads.py --input my_scan.json --dry-run

# Step 4: Confirm (after user approval)
python scripts/lock_archive_threads.py --input my_scan.json --confirm
```

### Exclude specific threads
```bash
python scripts/lock_archive_threads.py --input stale_threads.json --confirm \
  --exclude-ids 111222333444,555666777888
```

## Error Handling

All scripts follow these error handling conventions:
- **Rate limiting (429)**: Automatic retry with exponential backoff, respecting the `Retry-After` header
- **Permission errors (403)**: Logged and reported; the script continues with remaining threads
- **Not found (404)**: Thread was deleted; logged and skipped
- **Network errors**: Retried up to 3 times with increasing delays
- **Partial failures**: The script completes all possible operations and reports a summary of successes and failures at the end

## Further Reading

- `references/discord_api.md` — Discord API endpoints, authentication, pagination, and known quirks
- `references/workflow_guide.md` — Detailed step-by-step guide with troubleshooting tips
