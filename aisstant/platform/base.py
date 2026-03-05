"""Abstract interfaces for platform-specific functionality."""

from __future__ import annotations

from abc import ABC, abstractmethod


class StealthProvider(ABC):
    """Controls window visibility in OS-level features (screenshots, task switcher, etc.)."""

    @abstractmethod
    def hide_from_dock(self) -> None:
        """Remove app from task switcher / dock."""

    @abstractmethod
    def make_window_stealthy(self, qt_widget) -> None:
        """Apply stealth properties to a single window."""

    @abstractmethod
    def apply_stealth_to_all_windows(self) -> None:
        """Apply stealth to all visible windows (including popups)."""
