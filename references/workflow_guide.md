# Workflow Guide — The Hacky Way

## Full Step-by-Step Walkthrough

### Prerequisites Check

```bash
# Discord installed?
which discord || ls /usr/share/discord/Discord

# Python 3.9+?
python3 --version

# Dependencies?
pip install -r requirements.txt

# xdotool (optional)?
which xdotool
```

---

## Phase 0: Startup

The controller handles everything automatically:

```python
from discord_controller import DiscordController

ctrl = DiscordController()
ctrl.full_startup()
```

What happens:
1. Checks if Discord is already running with CDP on port 9222
2. If not, finds the Discord binary and launches it with `--remote-debugging-port=9222`
3. Waits for Discord to start (~8 seconds)
4. Connects to the renderer via CDP WebSocket
5. Extracts your user token (localStorage → script tags → webpack cache)
6. Verifies the token by calling `/users/@me`
7. Returns True if everything worked

**If startup fails:**
- Make sure Discord is installed
- Make sure you're logged in to Discord
- Check if port 9222 is already in use: `lsof -i :9222`
- Try launching manually: `discord --remote-debugging-port=9222`

---

## Phase 1: Scan

```bash
python scripts/scan_threads.py --channel-id 123456789 --min-inactive-days 30
```

What happens:
1. Uses the extracted token to call Discord API
2. Fetches active threads for the channel
3. Fetches public archived threads (with full pagination)
4. Fetches private archived threads (with full pagination)
5. Deduplicates by thread ID
6. Analyzes each thread for inactivity, category, and age
7. Saves results to `stale_threads.json`

**Output fields:**
- `scan_metadata` — summary stats
- `all_threads` — raw thread data
- `stale_threads` — enriched stale thread records

---

## Phase 2: Report

```bash
python scripts/generate_report.py --input stale_threads.json --categorize
```

Generates a markdown report with:
- Key findings (total scanned, stale count)
- Age breakdown (30-60, 60-90, 90-180, 180+ days)
- Issue categories (auto-categorized by keywords)
- Full thread details

**Review this before proceeding.** The user decides what to do.

---

## Phase 3: Act

### Step 1: Dry Run (ALWAYS FIRST)

```bash
python scripts/lock_archive_threads.py --input stale_threads.json --dry-run
```

Shows what would happen without making changes.

### Step 2: User Confirmation

Ask the user to review the dry run and confirm:
- "yes" / "confirm" / "do it" → proceed
- Anything else → abort

### Step 3: Execute

```bash
python scripts/lock_archive_threads.py --input stale_threads.json --confirm
```

Locks and archives each thread:
1. Lock first (`PATCH /channels/{id}` with `{"locked": true}`)
2. Brief pause (0.3s)
3. Archive (`PATCH /channels/{id}` with `{"archived": true}`)
4. Delay between threads (default 1.0s)

### Step 4: Verify

```bash
# Re-scan to verify
python scripts/scan_threads.py --channel-id 123456789 --min-inactive-days 30 --output verify.json
```

---

## Advanced: Direct Controller Usage

### CDP DOM Manipulation

```python
ctrl = DiscordController()
ctrl.full_startup()

# Click a button
ctrl.cdp.click_element('[aria-label="More"]')

# Read text
title = ctrl.cdp.get_element_text('.channel-name')

# Type text
ctrl.cdp.type_in_element('[contenteditable="true"]', "Hello world")
```

### xdotool Fallback

```python
# Activate Discord window
ctrl.xdo.activate_discord()

# Type something
ctrl.xdo.send_keys("Hello!")
ctrl.xdo.send_key("Return")

# Click at coordinates
ctrl.xdo.click_at(500, 300)
```

---

## Troubleshooting

### Discord won't launch with CDP
```bash
# Kill existing Discord
pkill -f Discord

# Launch manually with debug port
/usr/share/discord/Discord --remote-debugging-port=9222 &

# Wait for startup
sleep 10

# Test CDP
curl http://127.0.0.1:9222/json
```

### Token extraction fails
- Make sure you're logged in to Discord
- Wait longer for Discord to fully load
- Try restarting Discord
- Check if Discord updated and changed the token storage location

### API returns 401
- Token expired, re-extract: `ctrl.extract_token()`
- User session may have been invalidated

### API returns 403
- Your user account lacks the required permissions
- Need MANAGE_THREADS to lock, READ_MESSAGE_HISTORY to scan

### Rate limited (429)
- Increase batch delay: `--batch-delay 2.0`
- The scripts handle this automatically but aggressive use can hit limits

### Threads not locking
- Lock must happen BEFORE archive
- Check `thread_metadata.locked` not the top-level `locked` field
- Some Discord builds have quirks — see `discord_api.md`
