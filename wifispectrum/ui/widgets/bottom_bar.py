"""Thin bottom status bar with operation state, timing and progress."""

from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ...core.constants import PALETTE
from ..theme import font
from .base import label, rgba, tint


class ScanPulse(QWidget):
    """Thin moving scan indicator shown while a scan is running."""

    def __init__(self, width: int = 72, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(width, 4)
        self._phase = 0.0
        self._active = False
        self._timer = QTimer(self)
        self._timer.setInterval(28)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_active(self, active: bool) -> None:
        if active != self._active:
            self._active = active
            self.update()

    def _tick(self) -> None:
        if self._active:
            self._phase = (self._phase + 0.045) % 1.0
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#10283A"))
        painter.drawRoundedRect(rect, 2, 2)
        if not self._active:
            painter.setBrush(QColor("#1C4356"))
            painter.drawRoundedRect(rect, 2, 2)
            painter.end()
            return
        seg = max(18.0, self.width() * 0.38)
        x = -seg + (self.width() + seg) * self._phase
        grad = QLinearGradient(x, 0, x + seg, 0)
        grad.setColorAt(0.0, tint(PALETTE["cyan"], 0.0))
        grad.setColorAt(0.5, QColor(PALETTE["cyan"]))
        grad.setColorAt(1.0, tint(PALETTE["cyan"], 0.0))
        painter.setBrush(grad)
        painter.drawRoundedRect(QRectF(x, 0, seg, self.height()), 2, 2)
        painter.end()


class BottomBar(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("BottomBar")
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 16, 0)
        layout.setSpacing(9)

        self.operation = label("Initialising", 9, PALETTE["text_secondary"], 500, 0.2)
        layout.addWidget(self.operation)

        self.pulse = ScanPulse(70)
        self.pulse.setVisible(False)
        layout.addWidget(self.pulse, 0, Qt.AlignmentFlag.AlignVCenter)

        self.sep1 = self._dot()
        layout.addWidget(self.sep1)

        self.last_update = label("Last update \u2014", 9, PALETTE["muted"], 400, 0.2)
        layout.addWidget(self.last_update)

        self.sep2 = self._dot()
        layout.addWidget(self.sep2)

        self.next_update = label("Next update in \u2014", 9, PALETTE["muted"], 400, 0.2)
        layout.addWidget(self.next_update)

        layout.addStretch(1)

        self.error_label = label("", 9, PALETTE["red"], 500, 0.2)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        self.mode = label("WI-FI SCAN", 8, PALETTE["cyan"], 600, 0.9)
        self.mode.setStyleSheet(
            f"color: {PALETTE['cyan']}; background: rgba(0,217,245,0.08);"
            f" border: 1px solid rgba(0,217,245,0.26); border-radius: 6px; padding: 1px 6px;"
        )
        layout.addWidget(self.mode)

        self.state = label("STOPPED", 8, PALETTE["muted"], 600, 0.9)
        self.state.setStyleSheet(
            f"color: {PALETTE['muted']}; background: rgba(100,127,145,0.10);"
            f" border: 1px solid rgba(100,127,145,0.26); border-radius: 6px; padding: 1px 6px;"
        )
        layout.addWidget(self.state)

    @staticmethod
    def _dot() -> QLabel:
        dot = QLabel("\u2022")
        dot.setFont(font(9))
        dot.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")
        return dot

    # -- API ---------------------------------------------------------------
    def set_operation(self, text: str) -> None:
        self.operation.setText(text)

    def set_scanning(self, scanning: bool) -> None:
        self.pulse.setVisible(scanning)
        self.pulse.set_active(scanning)

    def set_last_update(self, timestamp: float | None) -> None:
        if not timestamp:
            self.last_update.setText("Last update \u2014")
            return
        self.last_update.setText(f"Last update {time.strftime('%H:%M:%S', time.localtime(timestamp))}")

    def set_countdown(self, seconds: int | None) -> None:
        if seconds is None:
            self.next_update.setText("Next update \u2014")
        else:
            self.next_update.setText(f"Next update in {seconds}s")

    def set_state(self, state: str) -> None:
        colors = {
            "running": PALETTE["green"],
            "paused": PALETTE["yellow"],
            "stopped": PALETTE["muted"],
            "error": PALETTE["red"],
        }
        color = colors.get(state, PALETTE["muted"])
        self.state.setText(state.upper())
        self.state.setStyleSheet(
            f"color: {color}; background: {rgba(color, 0.10)};"
            f" border: 1px solid {rgba(color, 0.30)}; border-radius: 6px; padding: 1px 6px;"
        )

    def set_mode(self, text: str, color: str = PALETTE["cyan"]) -> None:
        self.mode.setText(text.upper())
        self.mode.setStyleSheet(
            f"color: {color}; background: {rgba(color, 0.08)};"
            f" border: 1px solid {rgba(color, 0.26)}; border-radius: 6px; padding: 1px 6px;"
        )

    def set_error(self, message: str | None) -> None:
        if message:
            short = message if len(message) <= 90 else message[:87] + "\u2026"
            self.error_label.setText(short)
            self.error_label.setToolTip(message)
            self.error_label.setVisible(True)
        else:
            self.error_label.setVisible(False)
