#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Building AIsstant for Windows..."

pyinstaller \
  --name AIsstant \
  --windowed \
  --onefile \
  --noconfirm \
  --collect-all sounddevice \
  --hidden-import aisstant.platform.windows \
  --add-data "icons;icons" \
  --icon icons/web/favicon.ico \
  main.py

echo "==> Done: dist/AIsstant.exe"
