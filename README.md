# Discord Thread Manager — The Hacky Way 🔓

[![Hacky Approach](https://img.shields.io/badge/Approach-Hacky%20%F0%9F%94%93-red?style=for-the-badge)](https://github.com/roman-ryzenadvanced/discord-thread-manager)
[![No Bot Token Needed](https://img.shields.io/badge/No%20Bot%20Token-Required-green?style=for-the-badge)](https://github.com/roman-ryzenadvanced/discord-thread-manager)
[![Tested with Codex](https://img.shields.io/badge/Tested%20with-Codex%20CLI-blue?style=for-the-badge)](https://rommark.dev/codex-launcher/)
[![Linux](https://img.shields.io/badge/Platform-Ubuntu%20Linux-FCC624?style=for-the-badge&logo=ubuntu&logoColor=black)](https://ubuntu.com)

[![z.ai 10% OFF](https://img.shields.io/badge/z.ai-Coding%20Plan%2010%25%20OFF-6366f1?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJ3aGl0ZSI+PHRleHQgeD0iNCIgeT0iMTgiIGZvbnQtc2l6ZT0iMTYiIGZpbGw9IndoaXRlIj56PC90ZXh0Pjwvc3ZnPg==)](https://rommark.dev/codex-launcher/)
[![Free API](https://img.shields.io/badge/Xiaomi%20Mimo%202.5%20Pro-FREE%20API-orange?style=for-the-badge)](https://rommark.dev/codex-launcher/)

# For TRAE IDE users, custom agent may be for your assistance:
[TRADE SOLO Discord Agent](https://github.com/roman-ryzenadvanced/discord-thread-manager.git)


> **No bot token. No Discord developer portal. No OAuth setup. No friction.**
>
> Launches Discord with Chrome DevTools Protocol (CDP), extracts your user token
> from the running session via JavaScript injection, and controls everything through
> the REST API + DOM manipulation + xdotool fallback.

---

## 🧠 How It Works

```
Discord Desktop (--remote-debugging-port=9222)
    │
    ├── CDP WebSocket → JS Injection → Token Extraction
    │   ├── localStorage.getItem('token')
    │   ├── Script tag regex parsing
    │   └── Webpack module cache getToken()
    │
    ├── Discord REST API (with extracted user token)
    │   ├── Scan threads (active + archived)
    │   ├── Lock & archive stale threads
    │   └── Send messages
    │
    └── xdotool fallback (when API fails)
        ├── Send keystrokes
        ├── Click coordinates
        └── Window management
```

### The "Proper" Way vs. The Hacky Way

| | Proper (Bot API) | **Hacky (This Repo)** |
|---|---|---|
| **Setup** | Create bot app, configure OAuth, invite | Just launch Discord |
| **Token** | Bot token from dev portal | Extracted from live session |
| **Auth** | `Bot <token>` header | User token (extracted via CDP) |
| **UI Control** | API only | API + CDP DOM + xdotool |
| **Rate Limits** | Well-documented | Same, plus CDP overhead |
| **TOS Risk** | None | ⚠️ User tokens = gray area |
| **Setup Time** | ~30 minutes | ~0 minutes |

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/roman-ryzenadvanced/discord-thread-manager.git
cd discord-thread-manager

# Install dependencies
pip install -r requirements.txt

# Optional: xdotool for UI fallback
sudo apt install xdotool

# Scan for stale threads (launches Discord, extracts token, scans)
python scripts/scan_threads.py --channel-id YOUR_CHANNEL_ID

# Generate a report
python scripts/generate_report.py --input stale_threads.json --categorize

# Dry run (see what would happen)
python scripts/lock_archive_threads.py --input stale_threads.json --dry-run

# Actually do it (after reviewing dry run!)
python scripts/lock_archive_threads.py --input stale_threads.json --confirm
```

---

## 🤖 Tested With AI Coding Tools

This skill was **successfully tested end-to-end** using:

### [Codex CLI + Custom AI Models → rommark.dev/codex-launcher](https://rommark.dev/codex-launcher/)

> **⭐ This is how we actually built and tested everything.**

The [Codex Launcher](https://rommark.dev/codex-launcher/) lets you run Codex CLI with
**custom AI models** instead of the default OpenAI ones:

- **xiaomi mimo 2.5 pro** — 🔥 [**FREE API — Limited time, no credit card**](https://rommark.dev/codex-launcher/)
- **z.ai GLM 5.1** — [**10% OFF coding plan**](https://rommark.dev/codex-launcher/)

### Other Supported Tools

| Tool | Status | Guide |
|------|--------|-------|
| **Codex CLI** | ✅ Tested & Working | [`ai-tool-guides/codex.md`](ai-tool-guides/codex.md) |
| **Claude Code** | ⚠️ Not tested by us | [`ai-tool-guides/claude-code.md`](ai-tool-guides/claude-code.md) |
| **OpenCode** | ⚠️ Not tested by us | [`ai-tool-guides/opencode.md`](ai-tool-guides/opencode.md) |
| **ZCode** | ⚠️ Not tested by us | [`ai-tool-guides/zcode.md`](ai-tool-guides/zcode.md) |
| **Antigravity** | ⚠️ Not tested by us | [`ai-tool-guides/antigravity.md`](ai-tool-guides/antigravity.md) |

> **Note:** We only tested with Codex CLI. The other tools should work since they all
> support the same `SKILL.md` skill format, but we haven't verified them ourselves.
> If you get one working, PRs welcome!

---

## 📁 Project Structure

```
discord-thread-manager/
├── SKILL.md                        # AI agent skill definition
├── README.md                       # You are here
├── scripts/
│   ├── discord_controller.py       # 🧠 Core: CDP bridge + token extraction + API client
│   ├── scan_threads.py             # Scan channels for stale threads
│   ├── generate_report.py          # Generate markdown/JSON reports
│   ├── lock_archive_threads.py     # Bulk lock & archive threads
│   └── utils.py                    # Analysis helpers (categorization, age buckets)
├── ai-tool-guides/
│   ├── codex.md                    # Codex CLI setup
│   ├── claude-code.md              # Claude Code setup
│   ├── opencode.md                 # OpenCode setup
│   ├── zcode.md                    # ZCode setup
│   └── antigravity.md              # Antigravity setup
├── references/
│   ├── cdp_protocol.md             # CDP reference & token extraction details
│   ├── discord_api.md              # Discord API quirks & pagination
│   └── workflow_guide.md           # Step-by-step workflow guide
├── requirements.txt
├── LICENSE
└── .gitignore
```

---

## 🔑 Token Extraction Deep Dive

The controller extracts your Discord user token from the running desktop session
using three methods (tried in order):

### 1. localStorage (fastest)
```javascript
localStorage.getItem('token')
```

### 2. Script Tag Parsing
```javascript
document.querySelector('script').textContent.match(/"token"\s*:\s*"([^"]{30,})"/)
```

### 3. Webpack Module Cache
```javascript
// Searches through webpackChunkdiscord_app for getToken() exports
```

If all three fail, check:
- Discord is fully loaded (wait longer after launch)
- You're logged in to Discord
- The CDP port isn't blocked

---

## 🛡️ Safety & Ethics

- **Always dry-run first** — `--dry-run` is the default
- **Explicit confirmation required** — `--confirm` only runs after user says "yes"
- **Lock before archive** — order matters for reliable behavior
- **Rate limit aware** — automatic retry with backoff on 429s
- **User tokens are against TOS** — this is for personal server maintenance only
- **Don't use for spam or abuse** — that's not cool

---

## 🐧 Platform Notes

- **Built for Ubuntu Linux** — uses xdotool and Linux-specific Discord paths
- **Discord desktop required** — doesn't work with web version alone
- **CDP debugging** — `--remote-debugging-port=9222` is a Chromium/Electron flag
- **May work on other Linux distros** — untested but likely compatible

---

## 🎯 Special Offers

### 🔥 Free Xiaomi Mimo 2.5 Pro API
[Get it now →](https://rommark.dev/codex-launcher/)

Limited time offer. No credit card needed. Use it with Codex CLI to power
your AI coding sessions with one of the best open models available.

### 💜 z.ai Coding Plan — 10% OFF
[Get the discount →](https://rommark.dev/codex-launcher/)

GLM 5.1 is a powerhouse for code generation. 10% off the coding plan
exclusively through our launcher.

---

## ⚙️ API Quirks Handled

| Quirk | Solution |
|-------|----------|
| `+00:00` vs `Z` timestamps | Normalized before pagination cursors |
| `locked` field location | Check `thread_metadata.locked`, not top-level |
| Lock before archive | Lock is set first, then archive flag |
| Auto-archived ≠ locked | Explicit lock applied even on archived threads |
| User token response differences | Handled in API client |
| Rate limits (429) | Auto-retry with `Retry-After` header |
| CDP connection failures | Graceful fallback with clear error messages |

---

## License

MIT — Hack responsibly.
