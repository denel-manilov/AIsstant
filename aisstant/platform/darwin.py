"""macOS platform implementation — full stealth via AppKit + private frameworks."""

from __future__ import annotations

import ctypes
import logging
import platform
import stat
import urllib.request
from pathlib import Path

from aisstant.platform.base import StealthProvider

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SYSTEM_AUDIO_BINARY = _PROJECT_ROOT / "bin" / "SystemAudioDump"

_SYSTEM_AUDIO_RELEASE_URL = (
    "https://github.com/sohzm/systemAudioDump/releases/download/v1"
)
_SYSTEM_AUDIO_ASSETS = {
    "arm64": "SystemAudioDump",
    "x86_64": "SystemAudioDump_x86",
}

_skylight = None
_coregraphics = None


def _load_private_libs():
    global _skylight, _coregraphics
    if _skylight is not None:
        return
    _skylight = ctypes.cdll.LoadLibrary(
        "/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight"
    )
    _skylight.SLSMainConnectionID.restype = ctypes.c_int
    _coregraphics = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
    )
    _coregraphics.CGSSetWindowSharingState.restype = ctypes.c_int
    _coregraphics.CGSSetWindowSharingState.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    ]


class DarwinStealth(StealthProvider):
    def hide_from_dock(self) -> None:
        try:
            from AppKit import NSApp, NSApplicationActivationPolicyAccessory

            NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except Exception as e:
            logger.warning("Failed to hide from Dock: %s", e)

    def make_window_stealthy(self, qt_widget) -> None:
        try:
            from AppKit import NSApp, NSWindowSharingNone
            from Cocoa import (
                NSWindowCollectionBehaviorCanJoinAllSpaces,
                NSWindowCollectionBehaviorFullScreenNone,
                NSWindowCollectionBehaviorIgnoresCycle,
                NSWindowCollectionBehaviorStationary,
            )

            qt_widget.winId()

            target = None
            for nswindow in NSApp.windows():
                if nswindow.isVisible():
                    target = nswindow

            if target is None:
                logger.warning("No visible NSWindow found for stealth setup")
                return

            wid = target.windowNumber()

            target.setSharingType_(NSWindowSharingNone)
            target.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorStationary
                | NSWindowCollectionBehaviorIgnoresCycle
                | NSWindowCollectionBehaviorFullScreenNone
            )

            try:
                _load_private_libs()
                conn = _skylight.SLSMainConnectionID()
                _coregraphics.CGSSetWindowSharingState(conn, wid, 0)
            except Exception as e:
                logger.debug("CGSSetWindowSharingState failed: %s", e)

            logger.debug("Stealth properties applied to window %d", wid)
        except Exception as e:
            logger.warning("Failed to apply stealth properties: %s", e)

    def apply_stealth_to_all_windows(self) -> None:
        try:
            from AppKit import NSApp, NSWindowSharingNone

            _load_private_libs()
            conn = _skylight.SLSMainConnectionID()
            for nswindow in NSApp.windows():
                if nswindow.isVisible():
                    nswindow.setSharingType_(NSWindowSharingNone)
                    wid = nswindow.windowNumber()
                    _coregraphics.CGSSetWindowSharingState(conn, wid, 0)
        except Exception as e:
            logger.debug("apply_stealth_to_all_windows failed: %s", e)


def ensure_system_audio_binary() -> bool:
    if SYSTEM_AUDIO_BINARY.is_file():
        return True

    arch = platform.machine()
    asset_name = _SYSTEM_AUDIO_ASSETS.get(arch)
    if asset_name is None:
        logger.warning(
            "SystemAudioDump: unsupported architecture %s, skipping download",
            arch,
        )
        return False

    url = f"{_SYSTEM_AUDIO_RELEASE_URL}/{asset_name}"
    logger.info("Downloading SystemAudioDump for %s from %s", arch, url)

    try:
        SYSTEM_AUDIO_BINARY.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, SYSTEM_AUDIO_BINARY)
        SYSTEM_AUDIO_BINARY.chmod(
            SYSTEM_AUDIO_BINARY.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP,
        )
        logger.info("SystemAudioDump downloaded to %s", SYSTEM_AUDIO_BINARY)
        return True
    except Exception as exc:
        logger.error("Failed to download SystemAudioDump: %s", exc)
        if SYSTEM_AUDIO_BINARY.exists():
            SYSTEM_AUDIO_BINARY.unlink()
        return False
