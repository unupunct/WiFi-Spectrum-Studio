"""Channel Distribution chart: animated, hoverable, band aware."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ...core import channels
from ...core.constants import PALETTE
from ...core.models import Band
from ..theme import font
from .base import tint

# channel-group colours
_GROUP_COLORS = {
    "primary": PALETTE["cyan"],
    "secondary": PALETTE["blue"],
    "tertiary": PALETTE["purple"],
    "edge": PALETTE["text_secondary"],
}


class ChannelDistributionChart(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._band = Band.GHZ_24
        self._counts: dict[int, int] = {}
        self._avg_rssi: dict[int, float] = {}
        self._channels: list[int] = []
        self._display: dict[int, float] = {}
        self._target: dict[int, float] = {}
        self._max_value = 4
        self._hover = -1
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._animate)

    # -- data --------------------------------------------------------------
    def set_band(self, band: Band) -> None:
        if band is not self._band:
            self._band = band
            self._display.clear()
            self._counts = {}
            self._channels = []
            self.update()

    def set_data(self, counts: dict[int, int], band: Band, avg_rssi: dict[int, float] | None = None) -> None:
        if band is not self._band:
            self.set_band(band)
        self._counts = dict(counts)
        self._avg_rssi = avg_rssi or {}
        self._channels = self._visible_channels()
        self._max_value = max([4] + list(self._counts.values()))
        self._target = {ch: float(self._counts.get(ch, 0)) for ch in self._channels}
        for ch in self._channels:
            self._display.setdefault(ch, 0.0)
        self._display = {ch: self._display.get(ch, 0.0) for ch in self._channels}
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def _visible_channels(self) -> list[int]:
        supported = channels.band_channels(self._band)
        if self._band is Band.GHZ_24:
            return supported
        active = [ch for ch, count in self._counts.items() if count > 0]
        if not active:
            step = max(1, len(supported) // 16)
            return supported[::step]
        indices = [supported.index(ch) for ch in active if ch in supported]
        lo = max(0, min(indices) - 2)
        hi = min(len(supported), max(indices) + 3)
        window = supported[lo:hi]
        if len(window) > 26:
            center = (min(indices) + max(indices)) // 2
            window = supported[max(0, center - 13) : center + 13]
        return window

    def _animate(self) -> None:
        moving = False
        for ch in self._channels:
            current = self._display.get(ch, 0.0)
            target = self._target.get(ch, 0.0)
            if abs(target - current) > 0.02:
                self._display[ch] = current + (target - current) * 0.24
                moving = True
            else:
                self._display[ch] = target
        self.update()
        if not moving:
            self._timer.stop()

    # -- geometry ----------------------------------------------------------
    def _plot_rect(self) -> QRectF:
        return QRectF(26, 18, max(10, self.width() - 34), max(10, self.height() - 44))

    def _bar_rects(self) -> list[tuple[int, QRectF]]:
        plot = self._plot_rect()
        count = max(1, len(self._channels))
        slot = plot.width() / count
        bar_w = max(4.0, slot * 0.72)
        out: list[tuple[int, QRectF]] = []
        for index, ch in enumerate(self._channels):
            value = self._display.get(ch, 0.0)
            height = plot.height() * (value / max(1, self._max_value))
            x = plot.left() + slot * index + (slot - bar_w) / 2
            y = plot.bottom() - height
            out.append((ch, QRectF(x, y, bar_w, height)))
        return out

    def _bar_color(self, channel: int) -> str:
        if self._band is Band.GHZ_24:
            if channel in (1, 6, 11):
                return PALETTE["cyan"]
            if channel in (2, 7, 12):
                return PALETTE["blue"]
            if channel in (3, 8, 13):
                return PALETTE["purple"]
            return PALETTE["text_secondary"]
        index = self._channels.index(channel) if channel in self._channels else 0
        palette = [PALETTE["cyan"], PALETTE["blue"], PALETTE["purple"], PALETTE["green"]]
        return palette[(index // 4) % len(palette)]

    # -- painting ----------------------------------------------------------
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        plot = self._plot_rect()

        painter.setFont(font(8))
        painter.setPen(QColor(PALETTE["muted"]))
        tick_step = 1 if self._max_value <= 5 else max(1, self._max_value // 4)
        for value in range(0, self._max_value + 1, tick_step):
            y = plot.bottom() - plot.height() * value / max(1, self._max_value)
            painter.setPen(QPen(tint(PALETTE["blue"], 0.10), 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor(PALETTE["muted"]))
            text = str(value)
            painter.drawText(
                QRectF(0, y - 6, plot.left() - 7, 12),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                text,
            )

        if not self._channels or not any(self._counts.values()):
            painter.setFont(font(10))
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "No channel observations in this band")
            painter.end()
            return

        for channel, rect in self._bar_rects():
            color = self._bar_color(channel)
            hovered = channel == self._hover
            if rect.height() < 1:
                continue
            if hovered:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(tint(color, 0.16))
                painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 4, 4)
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0.0, QColor(color))
            grad.setColorAt(1.0, tint(color, 0.22))
            painter.setBrush(grad)
            pen = QPen(tint(color, 0.75))
            pen.setWidthF(1.0)
            painter.setPen(pen)
            radius = min(4.0, rect.width() / 2)
            painter.drawRoundedRect(rect, radius, radius)

            value = int(round(self._display.get(channel, 0.0)))
            if value > 0:
                painter.setFont(font(8, 600))
                painter.setPen(QColor(PALETTE["text"] if hovered else PALETTE["text_secondary"]))
                painter.drawText(
                    QRectF(rect.center().x() - 14, rect.top() - 14, 28, 12),
                    Qt.AlignmentFlag.AlignCenter,
                    str(value),
                )

        # x labels
        count = max(1, len(self._channels))
        slot = plot.width() / count
        painter.setFont(font(8, 500))
        for index, channel in enumerate(self._channels):
            x = plot.left() + slot * index + slot / 2
            painter.setPen(QColor(PALETTE["cyan"] if channel == self._hover else PALETTE["muted"]))
            painter.drawText(
                QRectF(x - slot / 2, plot.bottom() + 5, slot, 12),
                Qt.AlignmentFlag.AlignCenter,
                str(channel),
            )

        painter.setPen(QPen(QColor("#123246"), 1))
        painter.drawLine(QPointF(plot.left(), plot.bottom()), QPointF(plot.right(), plot.bottom()))

        if self._hover in self._counts:
            self._draw_hover_tip(painter, plot)
        painter.end()

    def _draw_hover_tip(self, painter: QPainter, plot: QRectF) -> None:
        channel = self._hover
        avg = self._avg_rssi.get(channel)
        text = f"CH {channel}  \u2022  {self._counts.get(channel, 0)} APs"
        if avg is not None:
            text += f"  \u2022  avg {avg:.0f} dBm"
        painter.setFont(font(8, 500, 0.3))
        width = painter.fontMetrics().horizontalAdvance(text) + 16
        rect = QRectF(plot.right() - width, plot.top() - 12, width, 18)
        painter.setBrush(tint("#04121F", 0.92))
        painter.setPen(QPen(tint(PALETTE["cyan"], 0.45), 1))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QColor(PALETTE["text_secondary"]))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def mouseMoveEvent(self, event) -> None:
        hover = -1
        for channel, rect in self._bar_rects():
            if rect.adjusted(-4, -6, 4, 4).contains(event.position()):
                hover = channel
                break
        if hover != self._hover:
            self._hover = hover
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = -1
        self.update()
        super().leaveEvent(event)
