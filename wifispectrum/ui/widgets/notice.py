"""Inline notice banner for errors, empty states and demo-mode warnings."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QWidget

from ...core.constants import PALETTE
from .. import icons
from .base import IconButton, label, rgba


class NoticeBar(QFrame):
    action_triggered = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setVisible(False)
        self._color = PALETTE["yellow"]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 8, 7)
        layout.setSpacing(9)
        self.icon = label("", 10)
        layout.addWidget(self.icon)
        self.text = label("", 9.5, PALETTE["text_secondary"], 500, 0.1, wrap=True)
        layout.addWidget(self.text, 1)
        self.action = QPushButton("Open Hardware")
        self.action.setObjectName("Ghost")
        self.action.setFixedHeight(24)
        self.action.setStyleSheet("padding: 2px 10px; font-size: 9px;")
        self.action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action.clicked.connect(self.action_triggered.emit)
        layout.addWidget(self.action)
        self.close_button = IconButton("close", "Dismiss", 22, 12)
        self.close_button.clicked.connect(lambda: self.setVisible(False))
        layout.addWidget(self.close_button)

    def show_message(
        self,
        message: str,
        severity: str = "warning",
        action_text: str = "Open Hardware",
    ) -> None:
        colors = {
            "warning": PALETTE["yellow"],
            "error": PALETTE["red"],
            "info": PALETTE["cyan"],
            "good": PALETTE["green"],
        }
        self._color = colors.get(severity, PALETTE["yellow"])
        self.setStyleSheet(
            f"NoticeBar {{ background: {rgba(self._color, 0.07)}; border: 1px solid {rgba(self._color, 0.30)};"
            f" border-radius: 8px; }}"
        )
        icon_name = "alert" if severity in ("warning", "error") else "info"
        self.icon.setPixmap(icons.pixmap(icon_name, self._color, 14, self.devicePixelRatioF()))
        self.text.setText(message)
        self.text.setStyleSheet(f"color: {PALETTE['text_secondary']}; background: transparent;")
        if action_text:
            self.action.setText(action_text)
            self.action.setVisible(True)
        else:
            self.action.setVisible(False)
        self.setVisible(True)
