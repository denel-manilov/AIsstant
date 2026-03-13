#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Building AIsstant for Linux..."

pyinstaller \
  --name AIsstant \
  --onedir \
  --noconfirm \
  --collect-all sounddevice \
  --hidden-import aisstant.platform.linux \
  --add-data "icons:icons" \
  main.py

# --- AppDir structure ---
echo "==> Creating AppDir..."
mkdir -p AIsstant.AppDir/usr/bin
cp -r dist/AIsstant/* AIsstant.AppDir/usr/bin/

# AppRun launcher
cat > AIsstant.AppDir/AppRun << 'APPRUN'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export LD_LIBRARY_PATH="${HERE}/usr/bin:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/AIsstant" "$@"
APPRUN
chmod +x AIsstant.AppDir/AppRun

# .desktop entry
cat > AIsstant.AppDir/AIsstant.desktop << 'DESKTOP'
[Desktop Entry]
Name=AIsstant
Exec=AIsstant
Icon=AIsstant
Type=Application
Categories=Audio;Utility;
Comment=AI-powered audio overlay assistant
DESKTOP

cp icons/web/icon-512.png AIsstant.AppDir/AIsstant.png

# Download appimagetool and build the AppImage
echo "==> Downloading appimagetool..."
if [ ! -f appimagetool-x86_64.AppImage ]; then
  wget -q "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod +x appimagetool-x86_64.AppImage
fi

echo "==> Building AppImage..."
./appimagetool-x86_64.AppImage --appimage-extract-and-run \
  AIsstant.AppDir AIsstant-linux-x86_64.AppImage

echo "==> Done: AIsstant-linux-x86_64.AppImage"
