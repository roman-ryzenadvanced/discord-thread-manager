#!/bin/bash
# Install Discord Thread Manager GUI on Ubuntu
set -e

echo "🔓 Discord Thread Manager — Installer"
echo ""

# System deps
echo "[1/3] Installing system dependencies..."
sudo apt update
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 xdotool

# Python deps
echo "[2/3] Installing Python dependencies..."
pip3 install -r requirements-gui.txt

# Desktop entry
echo "[3/3] Installing desktop entry..."
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
sed -i "s|/opt/discord-thread-manager|$REPO_DIR|g" discord-thread-manager.desktop
mkdir -p ~/.local/share/applications
cp discord-thread-manager.desktop ~/.local/share/applications/

echo ""
echo "✓ Done! Find 'Discord Thread Manager' in your app menu, or run:"
echo "  python3 $REPO_DIR/gui/discord-gui.py"
