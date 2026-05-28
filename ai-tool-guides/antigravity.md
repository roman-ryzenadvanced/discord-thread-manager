# Antigravity Setup Guide

## ⚠️ Not Tested By Us

This tool was **not tested** by us. It should work with standard skill formats,
but we haven't verified it. If you get it working, let us know!

## What is Antigravity?

Antigravity is an AI coding assistant. Check their official docs for
skill/plugin support details.

## Installation

```bash
# Follow Antigravity's official installation instructions
# Check their GitHub or website for the latest
```

## Installing This Skill

```bash
# Check Antigravity's skill directory structure
# Typical approach:
mkdir -p ~/.antigravity/skills/discord-thread-manager
cp -r SKILL.md scripts/ references/ ~/.antigravity/skills/discord-thread-manager/
```

## Usage

```
> scan discord channel 123456789 for stale threads
> generate report from scan data
> lock and archive threads older than 30 days (dry run)
```

## Notes

- The skill is tool-agnostic — it's just SKILL.md + Python scripts
- Any AI tool that can read skill files and execute Python will work
- The magic is in the CDP approach, not the AI tool

## Recommended Alternative

We **know** this works with Codex CLI:
- [Codex Launcher →](https://rommark.dev/codex-launcher/)
- Free xiaomi mimo 2.5 pro API — limited time, no credit card
- z.ai GLM 5.1 — 10% OFF coding plan
