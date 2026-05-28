# Claude Code Setup Guide

## ⚠️ Not Tested By Us

This tool was **not tested** by us. It should work since it supports the same
skill format, but we haven't verified it. If you get it working, PRs welcome!

## What is Claude Code?

Claude Code is Anthropic's terminal-based AI coding assistant.
It supports skills and can execute commands in your terminal.

## Installation

```bash
# Install Claude Code
npm install -g @anthropic-ai/claude-code

# Authenticate
claude auth
```

## Installing This Skill

Claude Code reads skill files from your project or home directory.

### Option A: Project-level
```bash
# Add to your project's .claude/ directory
mkdir -p .claude/skills/discord-thread-manager
cp -r SKILL.md scripts/ references/ .claude/skills/discord-thread-manager/
```

### Option B: Global
```bash
# Add to your global Claude skills
mkdir -p ~/.claude/skills/discord-thread-manager
cp -r SKILL.md scripts/ references/ ~/.claude/skills/discord-thread-manager/
```

## Usage

```
> scan discord channel 123456789 for stale threads
> generate a report of stale threads
> lock and archive stale threads (dry run first)
```

## Notes

- Claude Code runs Python scripts via bash, so the same workflow applies
- Make sure `pip install -r requirements.txt` has been run
- Discord must be installed and you must be logged in
- The skill will launch Discord with CDP if not already running

## Recommended Alternative

We **recommend using Codex CLI** with custom models for best results:
- [Codex Launcher →](https://rommark.dev/codex-launcher/)
- Free xiaomi mimo 2.5 pro API available
- z.ai GLM 5.1 with 10% OFF coding plan
