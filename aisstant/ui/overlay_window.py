from __future__ import annotations

import uuid
from enum import IntFlag

from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QCursor, QFont, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from aisstant.platform import IS_MACOS
from aisstant.platform.fonts import MONOSPACE_FONT
from aisstant.ui.theme import ACCENT_COLOR, BG_COLOR, BORDER_RADIUS

WINDOW_WIDTH = 420
WINDOW_HEIGHT = 320
MIN_WIDTH = 300
MIN_HEIGHT = 200
_RESIZE_MARGIN = 8


class _Edge(IntFlag):
    NONE = 0
    LEFT = 1
    RIGHT = 2
    TOP = 4
    BOTTOM = 8


class UserMessageBlock(QFrame):
    """A user question/message block."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setStyleSheet(
            "UserMessageBlock {"
            "  background-color: rgba(30, 30, 60, 180);"
            "  border: 1px solid rgba(100, 100, 150, 0.3);"
            "  border-radius: 8px;"
            "}"
        )
        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setFont(QFont(MONOSPACE_FONT, 12, weight=QFont.Weight.Normal))
        self._label.setStyleSheet(
            "QLabel {"
            "  color: #b0b0ff; background: transparent; border: none;"
            "  padding: 4px;"
            "}"
        )
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(self._label)

    @property
    def full_text(self) -> str:
        return self._full_text

    def set_text(self, text: str) -> None:
        self._full_text = text
        self._label.setText(text)
        self._update_height()

    def _update_height(self) -> None:
        width = self._label.width()
        if width > 0:
            height = self._label.heightForWidth(width)
            if height > 0:
                self._label.setFixedHeight(height)
                return
        self._label.setFixedHeight(self._label.sizeHint().height())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_height()


class ResponseBlock(QFrame):
    """A single AI response block."""

    expansion_requested = pyqtSignal(str)

    _EXPAND_BTN_STYLE_DEFAULT = (
        "QPushButton { color: #888; background: rgba(40, 40, 70, 200);"
        " border: 1px solid rgba(86, 141, 229, 0.3); border-radius: 9px;"
        " font-size: 10px; font-weight: bold; }"
        "QPushButton:hover { color: #568de5; border-color: #568de5; }"
    )
    _EXPAND_BTN_STYLE_LOADING = (
        "QPushButton { color: #f0c040; background: rgba(40, 40, 70, 200);"
        " border: 1px solid rgba(240, 192, 64, 0.5); border-radius: 9px;"
        " font-size: 10px; font-weight: bold; }"
        "QPushButton:hover { color: #f5d060; border-color: #f5d060; }"
    )
    _EXPAND_BTN_STYLE_READY = (
        "QPushButton { color: #568de5; background: rgba(40, 40, 70, 200);"
        " border: 1px solid rgba(86, 141, 229, 0.6); border-radius: 9px;"
        " font-size: 10px; font-weight: bold; }"
        "QPushButton:hover { color: #7ab0ff; border-color: #7ab0ff; }"
    )
    _EXPAND_BTN_STYLE_ERROR = (
        "QPushButton { color: #e74c3c; background: rgba(40, 40, 70, 200);"
        " border: 1px solid rgba(231, 76, 60, 0.5); border-radius: 9px;"
        " font-size: 10px; font-weight: bold; }"
        "QPushButton:hover { color: #ff6b5a; border-color: #ff6b5a; }"
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._block_id = uuid.uuid4().hex
        self._full_text = ""
        self.setStyleSheet(
            "ResponseBlock {"
            "  background-color: rgba(15, 15, 30, 180);"
            "  border: 1px solid rgba(86, 141, 229, 0.3);"
            "  border-radius: 8px;"
            "}"
        )
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setFont(QFont(MONOSPACE_FONT, 12, weight=QFont.Weight.Normal))
        self._browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setStyleSheet(
            "QTextBrowser {"
            "  color: #e6e6e6; background: transparent; border: none;"
            "}"
        )
        self._browser.document().setDocumentMargin(0)
        self._browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(self._browser)

        self._expand_btn = QPushButton("?")
        self._expand_btn.setParent(self)
        self._expand_btn.setFixedSize(18, 18)
        self._expand_btn.setStyleSheet(self._EXPAND_BTN_STYLE_DEFAULT)
        self._expand_btn.clicked.connect(
            lambda: self.expansion_requested.emit(self._block_id),
        )
        self._expand_btn.hide()

    @property
    def block_id(self) -> str:
        return self._block_id

    @property
    def full_text(self) -> str:
        return self._full_text

    def append_chunk(self, text: str) -> None:
        self._full_text += text
        cursor = self._browser.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self._update_height()

    def render(self) -> None:
        self._browser.setMarkdown(self._full_text)
        self._update_height()

    def mark_complete(self) -> None:
        self._expand_btn.show()
        self._reposition_expand_btn()

    def set_expansion_status(self, status_name: str) -> None:
        style_map = {
            "pending": self._EXPAND_BTN_STYLE_DEFAULT,
            "loading": self._EXPAND_BTN_STYLE_LOADING,
            "ready": self._EXPAND_BTN_STYLE_READY,
            "error": self._EXPAND_BTN_STYLE_ERROR,
        }
        self._expand_btn.setStyleSheet(
            style_map.get(status_name, self._EXPAND_BTN_STYLE_DEFAULT),
        )

    def _update_height(self) -> None:
        doc_height = self._browser.document().size().toSize().height()
        self._browser.setFixedHeight(doc_height)

    def _reposition_expand_btn(self) -> None:
        self._expand_btn.move(self.width() - 22, self.height() - 22)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._reposition_expand_btn()


class OverlayWindow(QWidget):
    clear_requested = pyqtSignal()
    close_requested = pyqtSignal()
    commit_requested = pyqtSignal()
    device_changed = pyqtSignal(int)
    expansion_requested = pyqtSignal(str)
    settings_requested = pyqtSignal()
    skip_requested = pyqtSignal()
    text_submitted = pyqtSignal(str)
    toggle_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._drag_pos: QPoint | None = None
        self._resize_edge: _Edge = _Edge.NONE
        self._resize_origin: QPoint | None = None
        self._resize_geo = None
        self._setup_window()
        self._build_ui()
        self._position_bottom_right()

    # ── window setup ─────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if IS_MACOS:
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMouseTracking(True)

    def _position_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.right() - WINDOW_WIDTH - 20
        y = geo.bottom() - WINDOW_HEIGHT - 20
        self.move(x, y)

    # ── UI construction ──────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        layout.addLayout(self._build_header())
        layout.addWidget(self._build_scroll_area())
        layout.addWidget(self._build_text_input())
        layout.addLayout(self._build_controls())

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        title = QLabel("Realtime Overlay")
        title.setStyleSheet(
            f"color: {ACCENT_COLOR.name()}; font-size: 13px; font-weight: bold;"
        )
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet(
            "color: #888; font-size: 11px;"
        )
        close_btn = QPushButton("\u00d7")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { color: #888; background: transparent; border: none; "
            "font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { color: #e74c3c; }"
        )
        close_btn.clicked.connect(self.close_requested.emit)

        settings_btn = QPushButton("\u2699")
        settings_btn.setFixedSize(24, 24)
        settings_btn.setStyleSheet(
            "QPushButton { color: #888; background: transparent; border: none; "
            "font-size: 14px; }"
            "QPushButton:hover { color: #568de5; }"
        )
        settings_btn.clicked.connect(self.settings_requested.emit)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._status_label)
        header.addWidget(settings_btn)
        header.addWidget(close_btn)
        return header

    def _build_scroll_area(self) -> QScrollArea:
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QWidget#scroll_content { background: transparent; }"
            "QScrollBar:vertical {"
            "  width: 6px; background: transparent;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(86, 141, 229, 0.4); border-radius: 3px;"
            "}"
        )

        scroll_content = QWidget()
        scroll_content.setObjectName("scroll_content")
        self._blocks_layout = QVBoxLayout(scroll_content)
        self._blocks_layout.setContentsMargins(0, 0, 0, 0)
        self._blocks_layout.setSpacing(8)
        self._blocks_layout.addStretch()

        self._scroll_area.setWidget(scroll_content)
        self._current_block: ResponseBlock | None = None
        self._blocks: dict[str, ResponseBlock] = {}

        self._stick_to_bottom: bool = True
        vsb = self._scroll_area.verticalScrollBar()
        vsb.valueChanged.connect(self._on_scroll_value_changed)
        vsb.rangeChanged.connect(self._on_scroll_range_changed)

        return self._scroll_area

    def _build_text_input(self) -> QLineEdit:
        self._text_input = QLineEdit()
        self._text_input.setPlaceholderText("Type a question...")
        self._text_input.setEnabled(False)
        self._text_input.setStyleSheet(
            "QLineEdit {"
            "  background: rgba(40, 40, 70, 200); color: #e6e6e6;"
            "  border: 1px solid rgba(86, 141, 229, 0.3);"
            "  border-radius: 6px; padding: 6px 10px;"
            "  font-size: 12px;"
            "}"
            "QLineEdit:focus {"
            "  border: 1px solid rgba(86, 141, 229, 0.7);"
            "}"
            "QLineEdit:disabled {"
            "  color: #666; background: rgba(30, 30, 50, 200);"
            "}"
        )
        self._text_input.returnPressed.connect(self._on_text_submit)
        return self._text_input

    def _on_text_submit(self) -> None:
        text = self._text_input.text().strip()
        if text:
            self._text_input.clear()
            self.text_submitted.emit(text)

    def _build_controls(self) -> QHBoxLayout:
        controls = QHBoxLayout()

        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(180)
        self._device_combo.setStyleSheet(
            "QComboBox {"
            "  background: rgba(40, 40, 70, 200); color: #ccc;"
            "  border: 1px solid rgba(86, 141, 229, 0.3);"
            "  border-radius: 6px; padding: 4px 8px;"
            "}"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView {"
            "  background: #1a1a2e; color: #ccc;"
            "  selection-background-color: rgba(86, 141, 229, 0.5);"
            "}"
        )
        original_show_popup = self._device_combo.showPopup

        def _stealth_show_popup():
            original_show_popup()
            from aisstant.platform import stealth
            QTimer.singleShot(0, stealth.apply_stealth_to_all_windows)

        self._device_combo.showPopup = _stealth_show_popup
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)

        self._toggle_btn = QPushButton("Start")
        self._toggle_btn.setFixedWidth(80)
        self._toggle_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(86, 141, 229, 0.8); color: white;"
            "  border: none; border-radius: 6px; padding: 6px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:hover { background: rgba(86, 141, 229, 1.0); }"
        )
        self._toggle_btn.clicked.connect(self.toggle_requested.emit)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedWidth(60)
        self._clear_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(149, 165, 166, 0.8); color: white;"
            "  border: none; border-radius: 6px; padding: 6px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:hover { background: rgba(149, 165, 166, 1.0); }"
        )
        self._clear_btn.clicked.connect(self.clear_requested.emit)

        self._send_btn = QPushButton("Send")
        self._send_btn.setFixedWidth(60)
        self._send_btn.setVisible(False)
        self._send_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(46, 204, 113, 0.8); color: white;"
            "  border: none; border-radius: 6px; padding: 6px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:hover { background: rgba(46, 204, 113, 1.0); }"
        )
        self._send_btn.clicked.connect(self.commit_requested.emit)

        self._skip_btn = QPushButton("Skip")
        self._skip_btn.setFixedWidth(60)
        self._skip_btn.setVisible(False)
        self._skip_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(230, 126, 34, 0.8); color: white;"
            "  border: none; border-radius: 6px; padding: 6px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:hover { background: rgba(230, 126, 34, 1.0); }"
        )
        self._skip_btn.clicked.connect(self.skip_requested.emit)

        controls.addWidget(self._device_combo)
        controls.addStretch()
        controls.addWidget(self._clear_btn)
        controls.addWidget(self._send_btn)
        controls.addWidget(self._skip_btn)
        controls.addWidget(self._toggle_btn)
        return controls

    # ── public API ───────────────────────────────────────

    def clear_dialogue(self) -> None:
        """Clear all messages from the overlay."""
        while self._blocks_layout.count() > 1:
            item = self._blocks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._current_block = None
        self._blocks.clear()

    def set_devices(self, devices: list[tuple[int, str]]) -> None:
        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        for index, name in devices:
            self._device_combo.addItem(name, index)
        self._device_combo.blockSignals(False)

    def show_user_message(self, text: str) -> None:
        """Display a user question/message block."""
        block = UserMessageBlock()
        block.set_text(text)
        insert_index = self._blocks_layout.count() - 1
        self._blocks_layout.insertWidget(insert_index, block)

    def begin_response(self) -> None:
        block = ResponseBlock()
        block.expansion_requested.connect(self.expansion_requested.emit)
        insert_index = self._blocks_layout.count() - 1
        self._blocks_layout.insertWidget(insert_index, block)
        self._current_block = block
        self._blocks[block.block_id] = block

    @property
    def current_block_id(self) -> str | None:
        if self._current_block is None:
            return None
        return self._current_block.block_id

    def mark_current_block_complete(self) -> None:
        if self._current_block is not None:
            self._current_block.mark_complete()

    def set_block_expansion_status(self, block_id: str, status_name: str) -> None:
        block = self._blocks.get(block_id)
        if block is not None:
            block.set_expansion_status(status_name)

    def append_text(self, text: str) -> None:
        if self._current_block is None:
            self.begin_response()
        self._current_block.append_chunk(text)
        self._auto_scroll()

    def _auto_scroll(self) -> None:
        if self._stick_to_bottom:
            QTimer.singleShot(0, self._do_scroll)

    def _do_scroll(self) -> None:
        if not self._stick_to_bottom:
            return
        vsb = self._scroll_area.verticalScrollBar()
        vsb.setValue(vsb.maximum())

    def _on_scroll_value_changed(self, value: int) -> None:
        vsb = self._scroll_area.verticalScrollBar()
        self._stick_to_bottom = value >= vsb.maximum() - 20

    def _on_scroll_range_changed(self, _min: int, _max: int) -> None:
        if self._stick_to_bottom:
            self._scroll_area.verticalScrollBar().setValue(_max)

    def set_status(self, status: str) -> None:
        self._status_label.setText(status)

    def set_responding(self, active: bool) -> None:
        self._skip_btn.setVisible(active)
        if active:
            self._send_btn.setVisible(False)
            self._text_input.setEnabled(False)
        else:
            if self._toggle_btn.text() == "Stop":
                self._send_btn.setVisible(True)
                self._text_input.setEnabled(True)
            QTimer.singleShot(0, self._render_current_block)

    def _render_current_block(self) -> None:
        if self._current_block is not None:
            self._current_block.render()
            self._auto_scroll()

    def set_recording(self, active: bool) -> None:
        self._send_btn.setVisible(active)
        self._text_input.setEnabled(active)
        self._toggle_btn.setText("Stop" if active else "Start")
        btn_color = "rgba(231, 76, 60, 0.8)" if active else "rgba(86, 141, 229, 0.8)"
        hover_color = "rgba(231, 76, 60, 1.0)" if active else "rgba(86, 141, 229, 1.0)"
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {btn_color}; color: white;"
            f"  border: none; border-radius: 6px; padding: 6px;"
            f"  font-weight: bold;"
            f"}}"
            f"QPushButton:hover {{ background: {hover_color}; }}"
        )

    def get_selected_device_index(self) -> int | None:
        idx = self._device_combo.currentIndex()
        if idx < 0:
            return None
        return self._device_combo.itemData(idx)

    # ── painting ─────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            0.0, 0.0,
            float(self.width()), float(self.height()),
            BORDER_RADIUS, BORDER_RADIUS,
        )
        painter.fillPath(path, QBrush(BG_COLOR))
        painter.end()

    # ── dragging / resizing ──────────────────────────────

    def _edge_at(self, pos: QPoint) -> _Edge:
        edge = _Edge.NONE
        if pos.x() <= _RESIZE_MARGIN:
            edge |= _Edge.LEFT
        elif pos.x() >= self.width() - _RESIZE_MARGIN:
            edge |= _Edge.RIGHT
        if pos.y() <= _RESIZE_MARGIN:
            edge |= _Edge.TOP
        elif pos.y() >= self.height() - _RESIZE_MARGIN:
            edge |= _Edge.BOTTOM
        return edge

    @staticmethod
    def _cursor_for_edge(edge: _Edge) -> QCursor:
        if edge in (_Edge.LEFT, _Edge.RIGHT):
            return QCursor(Qt.CursorShape.SizeHorCursor)
        if edge in (_Edge.TOP, _Edge.BOTTOM):
            return QCursor(Qt.CursorShape.SizeVerCursor)
        if edge in (_Edge.LEFT | _Edge.TOP, _Edge.RIGHT | _Edge.BOTTOM):
            return QCursor(Qt.CursorShape.SizeFDiagCursor)
        if edge in (_Edge.RIGHT | _Edge.TOP, _Edge.LEFT | _Edge.BOTTOM):
            return QCursor(Qt.CursorShape.SizeBDiagCursor)
        return QCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        edge = self._edge_at(event.pos())
        if edge != _Edge.NONE:
            self._resize_edge = edge
            self._resize_origin = event.globalPosition().toPoint()
            self._resize_geo = self.geometry()
        else:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._resize_edge != _Edge.NONE and self._resize_origin is not None:
            delta = event.globalPosition().toPoint() - self._resize_origin
            geo = self._resize_geo
            new_x, new_y = geo.x(), geo.y()
            new_w, new_h = geo.width(), geo.height()

            if self._resize_edge & _Edge.LEFT:
                new_x = geo.x() + delta.x()
                new_w = geo.width() - delta.x()
            if self._resize_edge & _Edge.RIGHT:
                new_w = geo.width() + delta.x()
            if self._resize_edge & _Edge.TOP:
                new_y = geo.y() + delta.y()
                new_h = geo.height() - delta.y()
            if self._resize_edge & _Edge.BOTTOM:
                new_h = geo.height() + delta.y()

            if new_w >= MIN_WIDTH and new_h >= MIN_HEIGHT:
                self.setGeometry(new_x, new_y, new_w, new_h)
        elif self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        else:
            edge = self._edge_at(event.pos())
            if edge != _Edge.NONE:
                self.setCursor(self._cursor_for_edge(edge))
            else:
                self.unsetCursor()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_pos = None
        self._resize_edge = _Edge.NONE
        self._resize_origin = None
        self._resize_geo = None

    # ── private ──────────────────────────────────────────

    def _on_device_changed(self, combo_index: int) -> None:
        device_index = self._device_combo.itemData(combo_index)
        if device_index is not None:
            self.device_changed.emit(device_index)
