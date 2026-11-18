"""Top status bar: live monitoring state, adapter, band and clock."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ...core.constants import PALETTE
from ...core.models import AdapterInfo, Band
from .. import icons
from ..theme import font, mono_family
from .base import IconButton, Pill, PulseDot, label, tint


class ContextChip(QWidget):
    """Compact clickable chip showing a caption and a value."""

    clicked = Signal()

    def __init__(self, icon_name: str, caption: str, width: int = 250, parent: QWidget | None = None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._caption = caption
        self._value = "--"
        self._sub = ""
        self._color = PALETTE["cyan"]
        self._hover = False
        self.setFixedHeight(34)
        self.setMinimumWidth(width)
        self.setMaximumWidth(width + 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_value(self, value: str, sub: str = "", color: str | None = None) -> None:
        self._value = value
        self._sub = sub
        if color:
            self._color = color
        self.update()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setBrush(tint(PALETTE["text"], 0.04) if self._hover else tint("#0A1826", 0.9))
        pen = QPen(tint(PALETTE["cyan"], 0.34) if self._hover else QColor("#14384A"))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 8, 8)

        painter.drawPixmap(9, int((self.height() - 15) / 2), icons.pixmap(self._icon_name, self._color, 15))

        painter.setFont(font(7, 600, 0.9))
        painter.setPen(QColor(PALETTE["muted"]))
        painter.drawText(QRectF(31, 6, 100, 9), Qt.AlignmentFlag.AlignLeft, self._caption.upper())

        painter.setFont(font(9.5, 500, 0.1))
        painter.setPen(QColor(PALETTE["text"]))
        value_width = self.width() - 38
        if self._sub:
            painter.setFont(font(9.5, 600, 0.1))
            painter.setPen(QColor(self._color))
            metrics = painter.fontMetrics()
            value = metrics.elidedText(self._value, Qt.TextElideMode.ElideRight, int(value_width * 0.55))
            painter.drawText(QRectF(31, 16, value_width * 0.55, 12), Qt.AlignmentFlag.AlignLeft, value)
            used = metrics.horizontalAdvance(value) + 34
            painter.setFont(font(8.5, 400, 0.1))
            painter.setPen(QColor(PALETTE["muted"]))
            sub = metrics.elidedText(self._sub, Qt.TextElideMode.ElideRight, int(max(20, self.width() - used - 10)))
            painter.drawText(
                QRectF(31 + used - 30, 16, max(20, self.width() - used - 3), 12),
                Qt.AlignmentFlag.AlignRight,
                sub,
            )
        else:
            painter.drawText(QRectF(31, 16, value_width, 12), Qt.AlignmentFlag.AlignLeft, self._value)
        painter.end()


class TopBar(QWidget):
    navigate = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(62)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 16, 0)
        layout.setSpacing(12)

        self.dot = PulseDot(PALETTE["green"], 8)
        layout.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)

        state_col = QWidget()
        state_layout = QHBoxLayout(state_col)
        state_layout.setContentsMargins(0, 0, 0, 0)
        state_layout.setSpacing(6)
        self.live_label = label("LIVE MONITORING", 9, PALETTE["green"], 600, 1.5)
        self.state_label = label("starting", 9, PALETTE["muted"], 500, 0.3)
        state_layout.addWidget(self.live_label)
        state_layout.addWidget(self.state_label)
        layout.addWidget(state_col)

        layout.addWidget(self._divider())

        self.adapter_chip = ContextChip("antenna", "Adapter", 286)
        self.adapter_chip.clicked.connect(lambda: self.navigate.emit("hardware"))
        layout.addWidget(self.adapter_chip)

        self.band_chip = ContextChip("frequency", "Band", 130)
        self.band_chip.clicked.connect(lambda: self.navigate.emit("spectrum"))
        layout.addWidget(self.band_chip)

        layout.addStretch(1)

        self.demo_pill = Pill("DEMO DATA", PALETTE["yellow"])
        self.demo_pill.setVisible(False)
        layout.addWidget(self.demo_pill)

        clock_col = QWidget()
        clock_layout = QHBoxLayout(clock_col)
        clock_layout.setContentsMargins(0, 0, 0, 0)
        clock_layout.setSpacing(6)
        self.clock = QLabel("00:00:00")
        self.clock.setFont(self._mono(12))
        self.clock.setStyleSheet(f"color: {PALETTE['text']};")
        self.date = QLabel("")
        self.date.setFont(font(7.5, 500, 0.6))
        self.date.setStyleSheet(f"color: {PALETTE['muted']};")
        clock_layout.addWidget(self.clock)
        clock_layout.addWidget(self.date)
        layout.addWidget(clock_col)

        self.settings_button = IconButton("settings", "Settings (Ctrl+,)", 28, 16)
        self.settings_button.clicked.connect(lambda: self.navigate.emit("settings"))
        layout.addWidget(self.settings_button)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start()
        self._update_clock()

    @staticmethod
    def _mono(size: int):
        f = font(size, 500, 0.4)
        f.setFamily(mono_family())
        return f

    def _divider(self) -> QFrame:
        frame = QFrame()
        frame.setFixedSize(1, 22)
        frame.setStyleSheet("background: #123246; border: none;")
        return frame

    def _update_clock(self) -> None:
        import time

        now = time.localtime()
        self.clock.setText(time.strftime("%H:%M:%S", now))
        self.date.setText(time.strftime("%d %b %Y", now).upper())

    # -- API ---------------------------------------------------------------
    def set_state(self, state: str, detail: str = "") -> None:
        mapping = {
            "running": (PALETTE["green"], "live monitoring"),
            "paused": (PALETTE["yellow"], "paused"),
            "stopped": (PALETTE["muted"], "stopped"),
            "error": (PALETTE["red"], "scan error"),
        }
        color, text = mapping.get(state, (PALETTE["muted"], state))
        self.dot.set_color(color)
        self.live_label.setStyleSheet(f"color: {color}; background: transparent;")
        self.live_label.setText(text.upper() if state != "running" else "LIVE MONITORING")
        self.state_label.setText(detail or ("scanning" if state == "running" else ""))

    def set_adapter(self, adapter: AdapterInfo | None) -> None:
        if adapter is None:
            self.adapter_chip.set_value("No adapter", "hardware unavailable", PALETTE["red"])
        else:
            self.adapter_chip.set_value(adapter.interface, adapter.name, PALETTE["cyan"])
        self.adapter_chip.setToolTip("Open Hardware")

    def set_band(self, band: Band) -> None:
        self.band_chip.set_value(band.label, "", band.color)
        self.band_chip.setToolTip("Open Live Spectrum")

    def set_demo(self, demo: bool) -> None:
        self.demo_pill.setVisible(demo)
        self.demo_pill.setToolTip(
            "Demonstration mode: every observation is simulated and clearly labelled."
        )
