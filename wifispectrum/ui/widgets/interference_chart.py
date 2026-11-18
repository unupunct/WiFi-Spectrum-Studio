"""Per-channel interference score bars used by the Channel Analyzer."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from ...core.constants import PALETTE
from ...core.models import Band
from ..theme import font
from .base import tint


class InterferenceChart(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._scores: list[tuple[int, float]] = []
        self._band = Band.GHZ_24
        self._recommended: int | None = None
        self.setMinimumHeight(96)

    def set_data(self, scores: list[tuple[int, float]], band: Band, recommended: int | None) -> None:
        self._scores = sorted(scores, key=lambda item: item[0])
        self._band = band
        self._recommended = recommended
        self.update()

    def _color(self, score: float) -> str:
        if score >= 0.7:
            return PALETTE["red"]
        if score >= 0.45:
            return PALETTE["orange"]
        if score >= 0.2:
            return PALETTE["yellow"]
        return PALETTE["green"]

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        plot = QRectF(2, 14, max(10, w - 4), max(10, h - 30))

        if not self._scores:
            painter.setFont(font(9.5))
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No channel scores yet")
            painter.end()
            return

        for step in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = plot.bottom() - plot.height() * step
            painter.setPen(QColor(tint(PALETTE["muted"], 0.18)))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        count = len(self._scores)
        slot = plot.width() / count
        bar_w = max(3.0, min(26.0, slot * 0.55))
        label_every = 1 if slot >= 20 else 2 if slot >= 12 else 4

        for index, (channel, score) in enumerate(self._scores):
            cx = plot.left() + slot * (index + 0.5)
            height = plot.height() * max(0.0, min(1.0, score))
            bar = QRectF(cx - bar_w / 2, plot.bottom() - height, bar_w, max(1.0, height))
            color = self._color(score)
            grad = QLinearGradient(bar.topLeft(), bar.bottomLeft())
            grad.setColorAt(0.0, tint(color, 0.95))
            grad.setColorAt(1.0, tint(color, 0.22))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawRoundedRect(bar, 2, 2)

            if channel == self._recommended:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QColor(tint(PALETTE["cyan"], 0.9)))
                painter.drawRoundedRect(bar.adjusted(-1.5, -1.5, 1.5, 1.5), 3, 3)

            if index % label_every == 0:
                painter.setFont(font(7, 500, 0.2))
                painter.setPen(QColor(PALETTE["text_secondary"] if channel == self._recommended else PALETTE["muted"]))
                painter.drawText(
                    QRectF(cx - 14, plot.bottom() + 3, 28, 11),
                    Qt.AlignmentFlag.AlignCenter,
                    str(channel),
                )
        painter.end()
