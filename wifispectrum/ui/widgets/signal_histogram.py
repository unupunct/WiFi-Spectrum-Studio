"""Signal-strength distribution histogram (observed networks per RSSI bucket)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from ...core.constants import PALETTE
from ..theme import font
from .base import tint

BUCKET_COLORS = ["#00E89A", "#00D9F5", "#FFC247", "#FF963D", "#FF7A6B"]


class SignalHistogram(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._data: list[tuple[str, int]] = []
        self._total = 0
        self.setMinimumHeight(110)

    def set_data(self, data: list[tuple[str, int]], total: int | None = None) -> None:
        self._data = list(data)
        self._total = int(total if total is not None else sum(v for _, v in data))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        plot = QRectF(2, 16, max(10, w - 4), max(10, h - 34))

        if not self._data or self._total <= 0:
            painter.setFont(font(9.5))
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No signal samples yet")
            painter.end()
            return

        peak = max(1, max(v for _, v in self._data))
        max_value = max(3, peak)
        painter.setFont(font(7.5, 500, 0.5))
        painter.setPen(QColor(tint(PALETTE["muted"], 0.55)))
        for step in range(0, max_value + 1, max(1, max_value // 2)):
            y = plot.bottom() - plot.height() * step / max_value
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        count = len(self._data)
        slot = plot.width() / max(1, count)
        bar_w = min(46.0, slot * 0.52)
        for index, (label_text, value) in enumerate(self._data):
            cx = plot.left() + slot * (index + 0.5)
            height = plot.height() * (value / max_value)
            bar = QRectF(cx - bar_w / 2, plot.bottom() - height, bar_w, max(0.0, height))
            color = BUCKET_COLORS[index % len(BUCKET_COLORS)]
            grad = QLinearGradient(bar.topLeft(), bar.bottomLeft())
            grad.setColorAt(0.0, tint(color, 0.95))
            grad.setColorAt(1.0, tint(color, 0.18))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawRoundedRect(bar, 3, 3)

            painter.setFont(font(9.5, 600, 0.2))
            painter.setPen(QColor(PALETTE["text"] if value else PALETTE["muted"]))
            painter.drawText(
                QRectF(cx - 20, bar.top() - 14, 40, 12),
                Qt.AlignmentFlag.AlignCenter,
                str(value),
            )
            painter.setFont(font(7.5, 500, 0.4))
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(
                QRectF(cx - slot / 2, plot.bottom() + 4, slot, 12),
                Qt.AlignmentFlag.AlignCenter,
                label_text,
            )
        painter.end()
