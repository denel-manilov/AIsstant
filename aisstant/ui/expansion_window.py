"""Popup window for displaying detailed topic expansions."""

from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from aisstant.pipeline.expansion_service import ExpansionResult, ExpansionStatus
from aisstant.platform.fonts import MONOSPACE_FONT
from aisstant.ui.base_window import StealthWindow
from aisstant.ui.theme import ACCENT_COLOR, BG_COLOR_SOLID

EXPANSION_WIDTH = 520
EXPANSION_HEIGHT = 450


class ExpansionWindow(StealthWindow):
    """Detailed topic expansion window with streaming support."""

    _bg_color = BG_COLOR_SOLID

    def __init__(self) -> None:
        super().__init__()
        self._block_id: str | None = None
        self.resize(EXPANSION_WIDTH, EXPANSION_HEIGHT)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        layout.addLayout(self._build_header())
        self._browser = self._build_browser()
        layout.addWidget(self._browser)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()

        title = QLabel("Details")
        title.setStyleSheet(
            f"color: {ACCENT_COLOR.name()}; font-size: 13px; font-weight: bold;"
        )

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")

        close_btn = QPushButton("\u00d7")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { color: #888; background: transparent; border: none;"
            " font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { color: #e74c3c; }"
        )
        close_btn.clicked.connect(self.close)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._status_label)
        header.addWidget(close_btn)
        return header

    def _build_browser(self) -> QTextBrowser:
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setFont(QFont(MONOSPACE_FONT, 12, weight=QFont.Weight.Normal))
        browser.setStyleSheet(
            "QTextBrowser {"
            "  color: #e6e6e6;"
            "  background-color: rgba(15, 15, 30, 180);"
            "  border: 1px solid rgba(86, 141, 229, 0.3);"
            "  border-radius: 8px;"
            "  padding: 10px;"
            "}"
            "QScrollBar:vertical {"
            "  width: 6px; background: transparent;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(86, 141, 229, 0.4); border-radius: 3px;"
            "}"
        )
        self._stick_to_bottom = True
        vsb = browser.verticalScrollBar()
        vsb.valueChanged.connect(self._on_scroll_value_changed)
        vsb.rangeChanged.connect(self._on_scroll_range_changed)
        return browser

    # ── public API ────────────────────────────────────

    @property
    def current_block_id(self) -> str | None:
        return self._block_id

    def show_for_block(self, block_id: str, result: ExpansionResult | None) -> None:
        self._block_id = block_id
        self._stick_to_bottom = True
        if result is not None:
            self.update_content(result)
        else:
            self._set_markdown("*Preparing...*")
            self._status_label.setText("Waiting")
        self.show()
        self.raise_()
        self.activateWindow()

    def update_content(self, result: ExpansionResult) -> None:
        match result.status:
            case ExpansionStatus.PENDING:
                self._set_markdown("*Preparing...*")
                self._status_label.setText("Waiting")
            case ExpansionStatus.LOADING:
                self._set_markdown(result.text or "*Generating...*")
                self._status_label.setText("Generating...")
            case ExpansionStatus.READY:
                self._set_markdown(result.text)
                self._status_label.setText("Ready")
            case ExpansionStatus.ERROR:
                self._set_markdown(f"**Error:** {result.error}")
                self._status_label.setText("Error")

    def _set_markdown(self, text: str) -> None:
        vsb = self._browser.verticalScrollBar()
        old_pos = vsb.value()
        self._browser.setMarkdown(text)
        if self._stick_to_bottom:
            QTimer.singleShot(0, self._do_scroll)
        else:
            vsb.setValue(old_pos)

    def _do_scroll(self) -> None:
        if not self._stick_to_bottom:
            return
        vsb = self._browser.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def _on_scroll_value_changed(self, value: int) -> None:
        vsb = self._browser.verticalScrollBar()
        self._stick_to_bottom = value >= vsb.maximum() - 20

    def _on_scroll_range_changed(self, _min: int, _max: int) -> None:
        if self._stick_to_bottom:
            self._browser.verticalScrollBar().setValue(_max)

