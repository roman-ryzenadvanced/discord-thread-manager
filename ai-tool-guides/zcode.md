# ZCode Setup Guide

## ⚠️ Not Tested By Us

This tool was **not tested** by us. It should work with the skill format,
but we haven't verified it. PRs welcome!

## What is ZCode?

ZCode is an AI-powered coding assistant. Check their docs for the latest
on skill support and configuration.

## Installation

```bash
# Follow ZCode's official installation guide
# Typically available as a VS Code extension or CLI
```

## Installing This Skill

```bash
# Check ZCode's documentation for skill installation paths
# Common pattern:
mkdir -p ~/.zcode/skills/discord-thread-manager
cp -r SKILL.md scripts/ references/ ~/.zcode/skills/discord-thread-manager/
```

## Usage

Once installed, reference the skill in your ZCode prompts:

```
> Use the discord-thread-manager skill to scan channel 123456789
> Generate a stale thread report with categories
> Dry-run lock and archive on threads older than 60 days
```

## Notes

- The Python scripts are self-contained and work independently
- Just make sure dependencies are installed: `pip install -r requirements.txt`
- Discord desktop must be running with CDP (the skill handles this)

## Recommended Alternative

Our verified setup: **Codex CLI** with custom models:
- [Codex Launcher →](https://rommark.dev/codex-launcher/)
- Free xiaomi mimo 2.5 pro API (no credit card)
- z.ai GLM 5.1 with 10% OFF coding plan
