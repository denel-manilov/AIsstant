from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from aisstant.config import (
    AVAILABLE_AGENT_MODELS,
    load_agent_model,
    load_api_key,
    load_custom_prompt,
    load_expansion_settings,
    load_few_shot_examples,
    save_agent_model,
    save_api_key,
    save_custom_prompt,
    save_expansion_settings,
    save_few_shot_examples,
)
from aisstant.platform.fonts import MONOSPACE_FONT
from aisstant.ui.base_window import StealthWindow
from aisstant.ui.theme import ACCENT_COLOR, BG_COLOR_SOLID

SETTINGS_WIDTH = 500
SETTINGS_HEIGHT = 720

_INPUT_STYLE = (
    "QLineEdit {"
    "  background-color: rgba(15, 15, 30, 180);"
    "  color: #e6e6e6;"
    "  border: 1px solid rgba(86, 141, 229, 0.3);"
    "  border-radius: 6px;"
    "  padding: 4px 8px;"
    "}"
)

_SECTION_LABEL_STYLE = (
    "color: #888; font-size: 11px; font-weight: bold;"
)

_GROUP_HEADER_STYLE = (
    "color: #568de5; font-size: 11px; font-weight: bold;"
    " letter-spacing: 1px; text-transform: uppercase;"
)

_SEPARATOR_STYLE = (
    "background-color: rgba(86, 141, 229, 0.2);"
    " min-height: 1px; max-height: 1px;"
)


class QAPairWidget(QFrame):
    remove_requested = pyqtSignal(object)

    def __init__(self, question: str = "", answer: str = "") -> None:
        super().__init__()
        self.setStyleSheet(
            "QAPairWidget {"
            "  background-color: rgba(15, 15, 30, 180);"
            "  border: 1px solid rgba(86, 141, 229, 0.3);"
            "  border-radius: 8px;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        q_row = QHBoxLayout()
        q_label = QLabel("Q:")
        q_label.setStyleSheet("color: #568de5; font-weight: bold; background: transparent; border: none;")
        q_label.setFixedWidth(20)
        self._q_input = QLineEdit(question)
        self._q_input.setFont(QFont(MONOSPACE_FONT, 12))
        self._q_input.setPlaceholderText("User question...")
        self._q_input.setStyleSheet(_INPUT_STYLE)

        remove_btn = QPushButton("\u2212")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet(
            "QPushButton { color: #888; background: transparent; border: none; "
            "font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { color: #e74c3c; }"
        )
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self))

        q_row.addWidget(q_label)
        q_row.addWidget(self._q_input)
        q_row.addWidget(remove_btn)

        a_row = QHBoxLayout()
        a_label = QLabel("A:")
        a_label.setStyleSheet("color: #2ecc71; font-weight: bold; background: transparent; border: none;")
        a_label.setFixedWidth(20)
        self._a_input = QLineEdit(answer)
        self._a_input.setFont(QFont(MONOSPACE_FONT, 12))
        self._a_input.setPlaceholderText("Expected answer...")
        self._a_input.setStyleSheet(_INPUT_STYLE)

        a_row.addWidget(a_label)
        a_row.addWidget(self._a_input)
        a_row.addSpacing(20)

        layout.addLayout(q_row)
        layout.addLayout(a_row)

    @property
    def question(self) -> str:
        return self._q_input.text().strip()

    @property
    def answer(self) -> str:
        return self._a_input.text().strip()


class SettingsWindow(StealthWindow):
    saved = pyqtSignal()

    _bg_color = BG_COLOR_SOLID

    def __init__(self) -> None:
        super().__init__()
        self._pairs: list[QAPairWidget] = []
        self.resize(SETTINGS_WIDTH, SETTINGS_HEIGHT)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        layout.addLayout(self._build_header())

        # ── System group ──
        layout.addWidget(self._make_group_header("System"))
        layout.addLayout(self._build_api_key_row())
        layout.addLayout(self._build_model_selector())

        prompt_label = QLabel("System Prompt:")
        prompt_label.setStyleSheet(_SECTION_LABEL_STYLE)
        layout.addWidget(prompt_label)

        self._editor = self._build_editor()
        layout.addWidget(self._editor, stretch=1)

        layout.addLayout(self._build_few_shot_header())
        layout.addWidget(self._build_pairs_container(), stretch=0)

        # ── Expansion group ──
        layout.addWidget(self._make_group_header("Expansion"))
        layout.addLayout(self._build_expansion_section())

        layout.addLayout(self._build_buttons())

    @staticmethod
    def _make_group_header(title: str) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 4, 0, 2)
        row.setSpacing(8)

        label = QLabel(title)
        label.setStyleSheet(_GROUP_HEADER_STYLE)

        line = QFrame()
        line.setStyleSheet(_SEPARATOR_STYLE)
        line.setFixedHeight(1)

        row.addWidget(label)
        row.addWidget(line, stretch=1)
        return container

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()

        title = QLabel("Prompt Settings")
        title.setStyleSheet(
            f"color: {ACCENT_COLOR.name()}; font-size: 13px; font-weight: bold;"
        )

        close_btn = QPushButton("\u00d7")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { color: #888; background: transparent; border: none; "
            "font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { color: #e74c3c; }"
        )
        close_btn.clicked.connect(self.close)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)
        return header

    def _build_editor(self) -> QTextEdit:
        editor = QTextEdit()
        editor.setFont(QFont(MONOSPACE_FONT, 12, weight=QFont.Weight.Normal))
        editor.setMinimumHeight(80)
        editor.setPlaceholderText(
            "Enter custom instructions for the AI assistant...\n\n"
            "This text will be appended to the default instructions."
        )
        editor.setStyleSheet(
            "QTextEdit {"
            "  background-color: rgba(15, 15, 30, 180);"
            "  color: #e6e6e6;"
            "  border: 1px solid rgba(86, 141, 229, 0.3);"
            "  border-radius: 8px;"
            "  padding: 8px;"
            "}"
        )
        return editor

    def _build_api_key_row(self) -> QHBoxLayout:
        row = QHBoxLayout()

        label = QLabel("API Key:")
        label.setStyleSheet(_SECTION_LABEL_STYLE)

        self._api_key_input = QLineEdit()
        self._api_key_input.setFont(QFont(MONOSPACE_FONT, 12))
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("sk-...")
        self._api_key_input.setStyleSheet(_INPUT_STYLE)

        row.addWidget(label)
        row.addWidget(self._api_key_input)
        return row

    def _build_model_selector(self) -> QHBoxLayout:
        row = QHBoxLayout()

        label = QLabel("Agent Model:")
        label.setStyleSheet(_SECTION_LABEL_STYLE)

        self._agent_model = QComboBox()
        self._agent_model.addItems(AVAILABLE_AGENT_MODELS)
        self._agent_model.setStyleSheet(
            "QComboBox {"
            "  background-color: rgba(15, 15, 30, 180);"
            "  color: #e6e6e6;"
            "  border: 1px solid rgba(86, 141, 229, 0.3);"
            "  border-radius: 6px;"
            "  padding: 4px 8px;"
            "}"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView {"
            "  background-color: rgba(26, 26, 46, 240);"
            "  color: #e6e6e6;"
            "  selection-background-color: rgba(86, 141, 229, 0.5);"
            "}"
        )
        self._agent_model.setMinimumWidth(160)

        row.addWidget(label)
        row.addWidget(self._agent_model)
        row.addStretch()
        return row

    def _build_expansion_section(self) -> QVBoxLayout:
        section = QVBoxLayout()
        section.setSpacing(4)

        top_row = QHBoxLayout()

        self._expansion_checkbox = QCheckBox("Enable")
        self._expansion_checkbox.setStyleSheet(
            "QCheckBox { color: #e6e6e6; font-size: 12px; }"
            "QCheckBox::indicator { width: 14px; height: 14px; }"
        )
        self._expansion_checkbox.toggled.connect(self._on_expansion_toggled)
        top_row.addWidget(self._expansion_checkbox)

        top_row.addStretch()

        model_label = QLabel("Model:")
        model_label.setStyleSheet(_SECTION_LABEL_STYLE)
        self._expansion_model = QComboBox()
        self._expansion_model.addItems([
            "gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4.1",
        ])
        self._expansion_model.setStyleSheet(
            "QComboBox {"
            "  background-color: rgba(15, 15, 30, 180);"
            "  color: #e6e6e6;"
            "  border: 1px solid rgba(86, 141, 229, 0.3);"
            "  border-radius: 6px;"
            "  padding: 4px 8px;"
            "}"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView {"
            "  background-color: rgba(26, 26, 46, 240);"
            "  color: #e6e6e6;"
            "  selection-background-color: rgba(86, 141, 229, 0.5);"
            "}"
        )
        self._expansion_model.setMinimumWidth(140)
        top_row.addWidget(model_label)
        top_row.addWidget(self._expansion_model)
        section.addLayout(top_row)

        prompt_label = QLabel("Expansion Prompt:")
        prompt_label.setStyleSheet(_SECTION_LABEL_STYLE)
        section.addWidget(prompt_label)

        self._expansion_prompt = QTextEdit()
        self._expansion_prompt.setFont(QFont(MONOSPACE_FONT, 11))
        self._expansion_prompt.setFixedHeight(80)
        self._expansion_prompt.setStyleSheet(
            "QTextEdit {"
            "  background-color: rgba(15, 15, 30, 180);"
            "  color: #e6e6e6;"
            "  border: 1px solid rgba(86, 141, 229, 0.3);"
            "  border-radius: 8px;"
            "  padding: 6px;"
            "}"
        )
        section.addWidget(self._expansion_prompt)

        user_prompt_label = QLabel("User Prompt ({text} = transcription):")
        user_prompt_label.setStyleSheet(_SECTION_LABEL_STYLE)
        section.addWidget(user_prompt_label)

        self._expansion_user_prompt = QTextEdit()
        self._expansion_user_prompt.setFont(QFont(MONOSPACE_FONT, 11))
        self._expansion_user_prompt.setFixedHeight(50)
        self._expansion_user_prompt.setStyleSheet(
            "QTextEdit {"
            "  background-color: rgba(15, 15, 30, 180);"
            "  color: #e6e6e6;"
            "  border: 1px solid rgba(86, 141, 229, 0.3);"
            "  border-radius: 8px;"
            "  padding: 6px;"
            "}"
        )
        section.addWidget(self._expansion_user_prompt)

        return section

    def _on_expansion_toggled(self, checked: bool) -> None:
        self._expansion_model.setEnabled(checked)
        self._expansion_prompt.setEnabled(checked)
        self._expansion_user_prompt.setEnabled(checked)

    def _build_few_shot_header(self) -> QHBoxLayout:
        row = QHBoxLayout()

        label = QLabel("Few-shot Examples:")
        label.setStyleSheet(_SECTION_LABEL_STYLE)

        add_btn = QPushButton("+ Add")
        add_btn.setFixedWidth(60)
        add_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(46, 204, 113, 0.8); color: white;"
            "  border: none; border-radius: 6px; padding: 4px;"
            "  font-size: 11px; font-weight: bold;"
            "}"
            "QPushButton:hover { background: rgba(46, 204, 113, 1.0); }"
        )
        add_btn.clicked.connect(lambda: self._add_pair())

        row.addWidget(label)
        row.addStretch()
        row.addWidget(add_btn)
        return row

    def _build_pairs_container(self) -> QWidget:
        container = QWidget()
        self._pairs_layout = QVBoxLayout(container)
        self._pairs_layout.setContentsMargins(0, 0, 0, 0)
        self._pairs_layout.setSpacing(6)
        self._pairs_layout.addStretch()
        return container

    def _build_buttons(self) -> QHBoxLayout:
        buttons = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(80)
        cancel_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(60, 60, 80, 0.8); color: #ccc;"
            "  border: none; border-radius: 6px; padding: 6px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:hover { background: rgba(60, 60, 80, 1.0); }"
        )
        cancel_btn.clicked.connect(self.close)

        save_btn = QPushButton("Save")
        save_btn.setFixedWidth(80)
        save_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(86, 141, 229, 0.8); color: white;"
            "  border: none; border-radius: 6px; padding: 6px;"
            "  font-weight: bold;"
            "}"
            "QPushButton:hover { background: rgba(86, 141, 229, 1.0); }"
        )
        save_btn.clicked.connect(self._on_save)

        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        return buttons

    # ── pair management ────────────────────────────────

    def _add_pair(self, question: str = "", answer: str = "") -> None:
        pair = QAPairWidget(question, answer)
        pair.remove_requested.connect(self._remove_pair)
        self._pairs.append(pair)
        insert_index = self._pairs_layout.count() - 1
        self._pairs_layout.insertWidget(insert_index, pair)

    def _remove_pair(self, pair: QAPairWidget) -> None:
        if pair in self._pairs:
            self._pairs.remove(pair)
            self._pairs_layout.removeWidget(pair)
            pair.deleteLater()

    def _clear_pairs(self) -> None:
        for pair in self._pairs:
            self._pairs_layout.removeWidget(pair)
            pair.deleteLater()
        self._pairs.clear()

    def _collect_examples(self) -> list[dict]:
        return [
            {"question": p.question, "answer": p.answer}
            for p in self._pairs
            if p.question and p.answer
        ]

    # ── save / load ────────────────────────────────────

    def _on_save(self) -> None:
        save_api_key(self._api_key_input.text().strip())
        save_agent_model(self._agent_model.currentText().strip())
        save_custom_prompt(self._editor.toPlainText())
        save_few_shot_examples(self._collect_examples())
        save_expansion_settings(
            enabled=self._expansion_checkbox.isChecked(),
            model=self._expansion_model.currentText().strip(),
            prompt=self._expansion_prompt.toPlainText(),
            user_prompt=self._expansion_user_prompt.toPlainText(),
        )
        self.saved.emit()
        self.close()

    # ── events ─────────────────────────────────────────

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._api_key_input.setText(load_api_key())
        self._agent_model.setCurrentText(load_agent_model())
        self._editor.setPlainText(load_custom_prompt())

        exp = load_expansion_settings()
        self._expansion_checkbox.setChecked(exp["enabled"])
        self._expansion_model.setCurrentText(exp["model"])
        self._expansion_prompt.setPlainText(exp["prompt"])
        self._expansion_user_prompt.setPlainText(exp["user_prompt"])
        self._on_expansion_toggled(exp["enabled"])

        self._clear_pairs()
        for ex in load_few_shot_examples():
            self._add_pair(ex.get("question", ""), ex.get("answer", ""))

