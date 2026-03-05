"""Base class for frameless, draggable, translucent overlay windows."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QBrush, QPainter, QPainterPath
from PyQt6.QtWidgets import QWidget

from aisstant.platform import IS_MACOS
from aisstant.ui.theme import BG_COLOR, BORDER_RADIUS


class StealthWindow(QWidget):
    """Frameless draggable window with rounded corners and translucent background.

    Subclasses can override ``_bg_color`` for a different alpha value.
    """

    _bg_color = BG_COLOR

    def __init__(self) -> None:
        super().__init__()
        self._drag_pos: QPoint | None = None
        self._setup_window_flags()

    def _setup_window_flags(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if IS_MACOS:
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            0.0, 0.0,
            float(self.width()), float(self.height()),
            BORDER_RADIUS, BORDER_RADIUS,
        )
        painter.fillPath(path, QBrush(self._bg_color))
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_pos = None
