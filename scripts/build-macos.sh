#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Building AIsstant for macOS..."

pyinstaller \
  --name AIsstant \
  --windowed \
  --onefile \
  --noconfirm \
  --collect-all sounddevice \
  --hidden-import aisstant.platform.darwin \
  --hidden-import aisstant.audio.system_capture \
  --add-data "icons:icons" \
  --icon icons/macos/AppIcon.icns \
  main.py

echo "==> Packaging AIsstant.app into zip..."
cd dist && zip -ry ../AIsstant-macos.zip AIsstant.app

echo "==> Done: AIsstant-macos.zip"
