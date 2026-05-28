# Workflow Guide: Discord Thread Cleanup

This guide walks through the complete end-to-end workflow for managing and cleaning
up stale Discord threads using an AI agent. It covers the full lifecycle from
initial setup through execution and verification.

## Table of Contents

1. [Setup](#setup)
2. [Phase 1: Scan](#phase-1-scan)
3. [Phase 2: Report](#phase-2-report)
4. [Phase 3: Act](#phase-3-act)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)
7. [Safety Checklist](#safety-checklist)

---

## Setup

### 1. Get a Discord Token

**For bots** (recommended):
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create or select an application
3. Go to the "Bot" tab and copy the token
4. Enable the "Message Content Intent" if you need to read message content
5. Invite the bot to your server with `MANAGE_THREADS` and `READ_MESSAGE_HISTORY` permissions

**Permissions checklist**:
- `MANAGE_THREADS` — Required to lock threads
- `READ_MESSAGE_HISTORY` — Required to scan thread messages
- `VIEW_CHANNEL` — Required to see the channel and its threads

### 2. Find Your Channel ID

1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click the channel → "Copy Channel ID"
3. This is the `--channel-id` parameter for all scripts

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your token and channel ID
```

Or export directly:
```bash
export DISCORD_TOKEN="your-token-here"
export DISCORD_CHANNEL_ID="123456789"
```

---

## Phase 1: Scan

Run the scanner to discover all threads and identify stale ones.

```bash
python scripts/scan_threads.py \
  --channel-id 123456789 \
  --min-inactive-days 30 \
  --output stale_threads.json
```

### What the Scanner Does

1. Fetches all active threads in the channel
2. Fetches all public archived threads (with full pagination)
3. Fetches all private archived threads (with full pagination)
4. Deduplicates by thread ID
5. Analyzes each thread for:
   - Last activity timestamp (from last message, archive time, or snowflake)
   - Message count
   - Thread state (archived, locked)
   - Category (by keyword matching)
6. Filters by the inactivity threshold
7. Outputs structured JSON

### What to Look For

- **Total threads scanned**: Does this match your expectation?
- **Stale thread count**: Is this reasonable?
- **Never-responded threads**: These represent gaps in support coverage
- **Age distribution**: Are there very old threads (180+ days) that were missed?

---

## Phase 2: Report

Generate a human-readable report from the scan data.

```bash
python scripts/generate_report.py \
  --input stale_threads.json \
  --categorize \
  --format markdown \
  --output stale_report.md
```

### Reviewing the Report

The report includes:

1. **Summary metrics** — Quick overview of the problem scope
2. **Age breakdown** — How stale are the threads?
3. **Issue categories** — What kinds of issues were abandoned?
4. **Thread details** — Full list with all metadata for each stale thread

### Decision Points

After reviewing the report, decide:

- **Should you adjust the threshold?** If 30 days catches too many active threads,
  increase to 60 or 90 days.
- **Should you exclude any threads?** Some threads may be intentionally kept open
  (e.g., pinned announcements, ongoing investigations). Note their IDs for the
  `--exclude-ids` parameter.
- **Should you proceed with locking?** Locking is irreversible for non-moderators
  — make sure you're confident.

---

## Phase 3: Act

### Step 1: Dry Run

Always start with a dry run to see exactly what will happen:

```bash
python scripts/lock_archive_threads.py \
  --input stale_threads.json \
  --dry-run
```

Review the dry run output carefully. It shows every thread that would be processed.

### Step 2: Get Confirmation

**Do not proceed without explicit user confirmation.** The user should review the
dry run output and explicitly say "yes", "confirm", or "do it" before continuing.

### Step 3: Execute

```bash
python scripts/lock_archive_threads.py \
  --input stale_threads.json \
  --confirm \
  --batch-delay 1.0
```

### Step 4: Handle Failures

If any threads fail, the script reports them at the end. Retry with:

```bash
python scripts/lock_archive_threads.py \
  --input stale_threads.json \
  --confirm \
  --retry-failed \
  --results-file lock_results_20240115_123456.json
```

---

## Verification

After processing, verify the results:

1. **Check the results JSON**: Review `lock_results_*.json` for any failures
2. **Spot-check in Discord**: Open a few threads and verify they're locked and archived
3. **Re-scan**: Run the scanner again to verify the thread states

```bash
# Re-scan to verify
python scripts/scan_threads.py \
  --channel-id 123456789 \
  --min-inactive-days 30 \
  --output verification_scan.json
```

Compare the new scan with the original. All previously stale threads should now
be both archived and locked.

---

## Troubleshooting

### "403 Forbidden" on Lock Operation

The token lacks `MANAGE_THREADS` permission. Either:
- Add the permission to the bot's role
- Use a token that has the permission
- Skip the lock and only archive (less ideal)

### Pagination Returns Empty Results

Likely the `+00:00` vs `Z` timestamp issue. The scanner handles this
automatically, but if you're making manual API calls, ensure timestamps
use the `Z` suffix.

### Lock Appears Not to Work

Check `thread_metadata.locked`, not the top-level `locked` field. Some tokens
return `None` at the top level even when the lock was successfully applied.
The scanner and action scripts handle this correctly.

### Rate Limit Errors (429)

Increase the `--batch-delay` parameter:

```bash
python scripts/lock_archive_threads.py --input stale_threads.json --confirm --batch-delay 2.0
```

### Thread Count Seems Wrong

The scanner fetches from three sources (active, public archived, private archived)
and deduplicates. If the count still seems off:
- Check if the token has access to all thread types
- Verify the channel ID is correct
- Some threads may be in different channels (threads can be moved)

---

## Safety Checklist

Before running any destructive operations, verify:

- [ ] Token has the correct permissions (`MANAGE_THREADS`, `READ_MESSAGE_HISTORY`)
- [ ] Channel ID is correct
- [ ] Scan results look reasonable (thread count, stale count)
- [ ] Report has been reviewed by a human
- [ ] Dry run output has been reviewed
- [ ] User has given explicit confirmation
- [ ] Any excluded thread IDs have been specified
- [ ] Backup of scan data exists (for audit trail)

### Data Safety

- All scan data is saved locally as JSON files — nothing is sent externally
- The scanner is read-only and makes no modifications
- The locker requires explicit `--confirm` flag
- All operations are logged with timestamps for audit purposes
- Results files include full details of every operation for accountability
