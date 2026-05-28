---
name: discord-thread-manager
description: >
  Manage Discord server threads — THE HACKY WAY. No bot token needed.
  Launches Discord with Chrome DevTools Protocol (CDP), extracts your user
  token from the live session via JavaScript injection, then uses the Discord
  REST API to scan, report, and bulk lock/archive stale threads.
  Works on Ubuntu Linux with Discord desktop installed.
  Also supports CDP DOM manipulation and xdotool UI fallback for full control.
  Use this skill for Discord thread management, stale thread cleanup,
  channel moderation automation, or any Discord control task on Linux.
---

# Discord Thread Manager — The Hacky Way 🔓

**No bot token. No Discord developer portal. No OAuth. No setup friction.**

This skill controls Discord by reverse-engineering the running desktop app:

1. **Launches Discord** with `--remote-debugging-port=9222` (Chrome DevTools Protocol)
2. **Connects via WebSocket** to the live Discord renderer process
3. **Extracts your token** from the running session via JavaScript injection into the renderer
4. **Uses that token** to hit Discord REST API directly
5. **CDP** for DOM manipulation, **xdotool** as a last-resort fallback for UI automation

## Why This Exists

The "proper" way to manage Discord threads requires creating a bot application,
configuring permissions, inviting it to your server, and managing tokens.
For personal server maintenance, that's overkill.

This approach: just launch Discord, yank the token, and go.

## ⚠️ Important Warnings

- **User tokens** are technically against Discord's Terms of Service
- This was built for **personal server management on Ubuntu Linux**
- Use at your own risk
- Don't use this for spam, harassment, or anything malicious
- **Tested successfully with [Codex](https://rommark.dev/codex-launcher/) + custom AI models** (xiaomi mimo 2.5 pro, z.ai GLM 5.1)

## Prerequisites

- **Discord desktop app** installed on Ubuntu Linux
- **Python 3.9+** with `requests` and `websocket-client` packages
- **xdotool** (optional, for UI automation fallback)
- **No bot token needed** — the skill extracts your user token automatically

```bash
# Install dependencies
pip install -r requirements.txt
# Optional: xdotool for UI fallback
sudo apt install xdotool
```

## How It Works (Architecture)

```
┌──────────────────────────────────���──────────────────┐
│                 Discord Desktop App                  │
│              (--remote-debugging-port=9222)          │
│                                                     │
│  ┌─────────────┐    ┌────────────────────────────┐  │
│  │  Renderer    │◄───│  CDP WebSocket (9222)      │  │
│  │  Process     │    │                            │  │
│  │              │    │  → JS Injection            │  │
│  │  localStorage│    │  → Token Extraction        │  │
│  │  webpack     │    │  → DOM Manipulation        │  │
│  │  scripts     │    │  → Click, Type, Read       │  │
│  └─────────────┘    └────────────────────────────┘  │
│                                                     │
└─────────────────────────────────────────────────────┘
                         │
                         │ Extracted user token
                         ▼
              ┌─────────────────────┐
              │  Discord REST API   │
              │  (api/v10)          │
              │                     │
              │  → List threads     │
              │  → Lock threads     │
              │  → Archive threads  │
              │  → Send messages    │
              └─────────────────────┘
                         │
                         │ If API fails
                         ▼
              ┌─────────────────────┐
              │  xdotool fallback   │
              │                     │
              │  → Send keystrokes  │
              │  → Click positions  │
              │  → Window activate  │
              └─────────────────────┘
```

## Core Workflow

The workflow has three phases. Always execute in order.

### Phase 1: Launch & Extract

```python
from discord_controller import DiscordController

ctrl = DiscordController()
ctrl.full_startup()  # Launches Discord → connects CDP → extracts token
```

This single call:
1. Checks if Discord is already running with CDP
2. If not, launches Discord with `--remote-debugging-port=9222`
3. Connects to the renderer via CDP WebSocket
4. Extracts your user token (tries localStorage → script tags → webpack cache)
5. Verifies the token by calling `/users/@me`

### Phase 2: Scan

```python
result = ctrl.scan_threads(channel_id="123456789", min_inactive_days=30)
```

Discovers all threads (active + public archived + private archived) and identifies stale ones.

```bash
# Or via CLI
python scripts/scan_threads.py --channel-id 123456789 --min-inactive-days 30
```

### Phase 3: Report

```bash
python scripts/generate_report.py --input stale_threads.json --categorize
```

**Always show the report to the user and get confirmation before Phase 4.**

### Phase 4: Act (Lock & Archive)

```bash
# ALWAYS dry-run first
python scripts/lock_archive_threads.py --input stale_threads.json --dry-run

# After user explicitly confirms
python scripts/lock_archive_threads.py --input stale_threads.json --confirm
```

**Safety requirements:**
1. ALWAYS run with `--dry-run` first
2. Get explicit user confirmation ("yes", "confirm", or "do it")
3. Never run `--confirm` without explicit go-ahead
4. Lock before archive — order matters

## Token Extraction Methods

The controller tries three methods in order:

### Method 1: localStorage
```javascript
localStorage.getItem('token')
```

### Method 2: Script tag parsing
```javascript
document.querySelector('script').textContent.match(/"token"\s*:\s*"([^"]{30,})"/)
```

### Method 3: Webpack module cache
```javascript
// Searches webpackChunkdiscord_app for getToken() exports
```

## CDP DOM Operations

Beyond the API, the controller can manipulate Discord's UI directly:

```python
ctrl.cdp.click_element('[aria-label="Thread Menu"]')
ctrl.cdp.type_in_element('[contenteditable="true"]', "Closing this thread")
ctrl.cdp.get_element_text('.thread-title')
```

## xdotool Fallback

When CDP/DOM methods fail:

```python
ctrl.xdo.activate_discord()
ctrl.xdo.send_keys("Hello!")
ctrl.xdo.send_key("Return")
ctrl.xdo.click_at(500, 300)
```

## Scripts Reference

| Script | Purpose | Auth |
|--------|---------|------|
| `discord_controller.py` | Core CDP + API controller | Extracts token from session |
| `scan_threads.py` | Discover and filter threads | Uses controller |
| `generate_report.py` | Produce reports from scan data | No auth needed |
| `lock_archive_threads.py` | Lock & archive stale threads | Uses controller |
| `utils.py` | Analysis helpers | No auth needed |

## Tested With

This skill was **successfully tested** using:
- **[Codex CLI](https://rommark.dev/codex-launcher/)** with custom AI models:
  - **xiaomi mimo 2.5 pro** — [Free API, limited time, no credit card](https://rommark.dev/codex-launcher/)
  - **z.ai GLM 5.1** — [10% OFF coding plan](https://rommark.dev/codex-launcher/)
- **Ubuntu Linux** (primary dev/testing environment)

Other AI coding tools (Claude Code, OpenCode, ZCode, Antigravity) are supported
via the skill format but have **not been tested** by us. See `ai-tool-guides/` for setup instructions.

## Further Reading

- `references/cdp_protocol.md` — CDP endpoints, authentication, token extraction details
- `references/discord_api.md` — Discord API endpoints, pagination, quirks
- `references/workflow_guide.md` — Step-by-step guide with troubleshooting
- `ai-tool-guides/` — Per-tool setup instructions (codex, claude code, opencode, etc.)
