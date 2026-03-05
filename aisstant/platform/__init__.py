"""Platform detection and provider exports."""

from __future__ import annotations

import sys

from aisstant.platform.base import StealthProvider

IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform == "linux"

SYSTEM_AUDIO_DEVICE_INDEX = -1

stealth: StealthProvider

if IS_MACOS:
    from aisstant.platform.darwin import DarwinStealth

    stealth = DarwinStealth()
elif IS_WINDOWS:
    from aisstant.platform.windows import WindowsStealth

    stealth = WindowsStealth()
else:
    from aisstant.platform.linux import LinuxStealth

    stealth = LinuxStealth()


def system_audio_available() -> bool:
    """Check whether system audio capture is available on the current platform."""
    if not IS_MACOS:
        return False
    from aisstant.platform.darwin import SYSTEM_AUDIO_BINARY

    return SYSTEM_AUDIO_BINARY.is_file()
