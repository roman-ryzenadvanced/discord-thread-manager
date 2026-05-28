# Discord Thread Manager

An AI agent skill for managing Discord server threads at scale. Scan for stale threads, generate detailed reports, and bulk lock & archive them — all through the Discord REST API.

## What It Does

- **Scan**: Discover all threads in a channel (active, archived public, archived private) with full pagination
- **Report**: Generate markdown/JSON reports with age breakdowns, issue categorization, and activity metrics
- **Act**: Bulk lock and archive stale threads with dry-run support, exclusion lists, and automatic rate-limit handling

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Discord token and channel ID

# Scan for stale threads (30+ days inactive)
python scripts/scan_threads.py --channel-id YOUR_CHANNEL_ID --min-inactive-days 30

# Generate a report
python scripts/generate_report.py --input stale_threads.json --categorize

# Dry run (see what would happen)
python scripts/lock_archive_threads.py --input stale_threads.json --dry-run

# Confirm (after reviewing the dry run)
python scripts/lock_archive_threads.py --input stale_threads.json --confirm
```

## Skill Usage

This project doubles as an **AI agent skill** compatible with Claude, Codex, OpenClaw, and other agent frameworks. The `SKILL.md` file contains the skill definition and instructions.

To use as a skill:
1. Copy the entire `discord-thread-manager/` directory into your agent's skill directory
2. The agent will automatically consult `SKILL.md` when thread management tasks arise
3. The scripts in `scripts/` handle all API interactions

## Project Structure

```
discord-thread-manager/
├── SKILL.md                    # Agent skill definition and instructions
├── scripts/
│   ├── scan_threads.py         # Discover and filter threads
│   ├── generate_report.py      # Produce reports from scan data
│   ├── lock_archive_threads.py # Bulk lock & archive threads
│   └── utils.py               # Shared API client and helpers
├── references/
│   ├── discord_api.md          # Discord API endpoints and quirks
│   └── workflow_guide.md       # Step-by-step workflow with troubleshooting
├── README.md
├── requirements.txt
├── LICENSE
├── .env.example
└── .gitignore
```

## Key Features

- **Full thread discovery**: Active + public archived + private archived, with complete pagination
- **Rate-limit safe**: Automatic retry with exponential backoff on 429 responses
- **Dry-run mode**: See exactly what will happen before making changes
- **Issue categorization**: Auto-categorize threads by keyword matching (subscription, billing, bug, API, etc.)
- **Exclusion support**: Skip specific threads by ID
- **Audit trail**: All operations logged with timestamps; results saved as JSON
- **Discord API quirks handled**: Timestamp normalization, metadata field locations, lock-before-archive ordering

## Discord API Quirks Handled

This project handles several non-obvious Discord API behaviors:

1. **`+00:00` vs `Z` timestamps**: Discord returns `+00:00` but expects `Z` for pagination cursors
2. **`locked` field location**: Lock status is in `thread_metadata.locked`, not the top-level `locked` field
3. **Lock before archive**: Locking must happen before archiving for reliable behavior
4. **Auto-archived ≠ locked**: Auto-archived threads still need explicit locking
5. **Token type differences**: Bot and user tokens may return different response structures

See `references/discord_api.md` for full details.

## Permissions Required

| Permission | Why |
|-----------|-----|
| `MANAGE_THREADS` | Required to lock threads |
| `READ_MESSAGE_HISTORY` | Required to scan thread content |
| `VIEW_CHANNEL` | Required to see the channel |

## License

MIT
