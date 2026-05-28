# OpenCode Setup Guide

## ⚠️ Not Tested By Us

This tool was **not tested** by us. It should work since it supports skill files,
but we haven't verified it. PRs welcome if you get it working!

## What is OpenCode?

OpenCode is an open-source terminal AI coding assistant.
It supports skill files and can run commands in your workspace.

## Installation

```bash
# Check the OpenCode repo for latest installation instructions
# Typically installed via go or a binary release
go install github.com/opencode-ai/opencode@latest
```

## Installing This Skill

```bash
# OpenCode looks for skills in the project's skill directory
mkdir -p .opencode/skills/discord-thread-manager
cp -r SKILL.md scripts/ references/ .opencode/skills/discord-thread-manager/
```

## Usage

```
> scan discord channel 123456789 for stale threads older than 30 days
> generate a categorized report
> lock and archive threads (dry run first)
```

## Notes

- Same prerequisites apply: Discord desktop, Python 3.9+, requirements.txt
- The skill works the same way regardless of which AI tool drives it
- All the heavy lifting is done by the Python scripts

## Recommended Alternative

We tested with **Codex CLI** + custom models:
- [Codex Launcher →](https://rommark.dev/codex-launcher/)
- Free xiaomi mimo 2.5 pro API (limited time)
- z.ai GLM 5.1 with 10% OFF
