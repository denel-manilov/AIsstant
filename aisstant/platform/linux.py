"""Linux platform implementation — noop stealth (always-on-top only)."""

from __future__ import annotations

import logging

from aisstant.platform.base import StealthProvider

logger = logging.getLogger(__name__)


class LinuxStealth(StealthProvider):
    def hide_from_dock(self) -> None:
        logger.debug("hide_from_dock: no-op on Linux")

    def make_window_stealthy(self, qt_widget) -> None:
        logger.debug("make_window_stealthy: no-op on Linux")

    def apply_stealth_to_all_windows(self) -> None:
        logger.debug("apply_stealth_to_all_windows: no-op on Linux")
