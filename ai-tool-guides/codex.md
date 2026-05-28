# Codex CLI Setup Guide

## ✅ Tested & Working

This skill was **successfully tested end-to-end** with Codex CLI.
This is the tool we used to build and verify everything.

## What is Codex CLI?

Codex is an open-source terminal-based AI coding assistant by OpenAI.
It runs in your terminal and can execute commands, edit files, and use skills.

## Installation

```bash
# Install Codex CLI
npm install -g @openai/codex

# Or via the launcher (recommended for custom models)
# See: https://rommark.dev/codex-launcher/
```

## Setting Up with Custom AI Models

The [Codex Launcher](https://rommark.dev/codex-launcher/) lets you run Codex
with non-OpenAI models. This is how we tested this skill.

### Xiaomi Mimo 2.5 Pro (FREE)
```bash
# Free API — limited time, no credit card needed
# Get your API key at the launcher page
export CODEX_MODEL="mimo-v2.5-pro"
# Configure via launcher settings
```

### z.ai GLM 5.1 (10% OFF)
```bash
# Get the coding plan with 10% discount
export CODEX_MODEL="glm-5.1"
# Configure via launcher settings
```

## Installing This Skill

```bash
# Clone the repo into your Codex skills directory
cd ~/.codex/skills/
git clone https://github.com/roman-ryzenadvanced/discord-thread-manager.git

# Or copy just the skill file
mkdir -p ~/.codex/skills/discord-thread-manager
cp SKILL.md scripts/ references/ ~/.codex/skills/discord-thread-manager/
```

## Usage

Once installed, Codex will automatically use this skill when you mention
Discord thread management:

```
> scan my discord channel 123456789 for stale threads older than 30 days
> generate a report of stale threads in that channel
> lock and archive all threads older than 90 days (dry run first)
```

## Our Testing Setup

```
Ubuntu 24.04 LTS
Discord Desktop (deb package)
Codex CLI + mimo-v2.5-pro model
Python 3.12
```

## Links

- **Codex Launcher**: https://rommark.dev/codex-launcher/
- **Free Mimo 2.5 Pro API**: https://rommark.dev/codex-launcher/
- **z.ai 10% OFF**: https://rommark.dev/codex-launcher/
