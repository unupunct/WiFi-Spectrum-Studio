"""Cross-band channel occupancy map.

Every cell is a real Wi-Fi channel positioned on its frequency; the fill shows
how many observed networks reported that channel. It is an occupancy map, not a
measured RF heat map.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from ...core import channels
from ...core.constants import PALETTE
from ...core.models import Band, ScanSnapshot
from ..theme import font
from .base import tint


class ChannelMap(QWidget):
    band_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._snapshot: ScanSnapshot | None = None
        self._cells: list[tuple[QRectF, Band, int, int]] = []
        self.setMinimumHeight(176)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_snapshot(self, snapshot: ScanSnapshot | None) -> None:
        self._snapshot = snapshot
        self.update()

    # -- geometry ----------------------------------------------------------
    def _lane_channels(self, band: Band, counts: dict[int, int]) -> list[int]:
        return channels.band_channels(band)

    def _build_cells(self) -> list[tuple[QRectF, Band, int, int]]:
        cells: list[tuple[QRectF, Band, int, int]] = []
        left = 66.0
        right = max(left + 20, self.width() - 8.0)
        lane_h = self.height() / 3.0
        for index, band in enumerate(Band.all()):
            lo, hi = channels.band_bounds(band)
            counts = self._snapshot.counts_by_channel(band) if self._snapshot else {}
            usable = min(72.0, lane_h - 18.0)
            top = index * lane_h + (lane_h - usable) / 2.0
            for channel in self._lane_channels(band, counts):
                centre = channels.channel_to_freq(band, channel)
                if not centre:
                    continue
                # 2.4 GHz channels sit 5 MHz apart and overlap heavily at 20 MHz
                # wide; narrow slots keep every channel legible on the map.
                half = 2.5 if band is Band.GHZ_24 else 10.0
                x0 = left + (right - left) * (centre - half - lo) / (hi - lo)
                x1 = left + (right - left) * (centre + half - lo) / (hi - lo)
                if x1 - x0 < 2.0:
                    continue
                cells.append((QRectF(x0, top, max(2.0, x1 - x0 - 1.4), usable), band, channel, counts.get(channel, 0)))
        return cells

    # -- painting ----------------------------------------------------------
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._cells = self._build_cells()
        lane_h = self.height() / 3.0

        for index, band in enumerate(Band.all()):
            y = index * lane_h
            mid = y + lane_h / 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(band.color))
            painter.drawEllipse(QPointF(4, mid - 12), 3.0, 3.0)
            painter.setFont(font(10, 600, 0.2))
            painter.setPen(QColor(PALETTE["text"]))
            painter.drawText(QPointF(14, mid - 7), band.label)
            count = len(self._snapshot.by_band(band)) if self._snapshot else 0
            painter.setFont(font(8, 500, 0.3))
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(QPointF(14, mid + 7), f"{count} AP{'s' if count != 1 else ''}")
            if index < 2:
                painter.setPen(QPen(QColor(tint(PALETTE["border"], 0.4)), 1))
                painter.drawLine(QPointF(0, y + lane_h), QPointF(self.width(), y + lane_h))

        for rect, band, channel, count in self._cells:
            color = self._cell_color(count)
            painter.setPen(QPen(QColor(tint(PALETTE["border"], 0.55)), 1))
            painter.setBrush(color)
            painter.drawRoundedRect(rect, 2.2, 2.2)
            if rect.width() >= 15:
                painter.setFont(font(7.2, 600, 0.2))
                label_color = "#04121F" if count >= 2 else (PALETTE["text"] if count else PALETTE["muted"])
                painter.setPen(QColor(label_color))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(channel))
        painter.end()

    @staticmethod
    def _cell_color(count: int) -> QColor:
        if count <= 0:
            return tint("#0B2130", 1.0)
        if count == 1:
            return tint(PALETTE["cyan"], 0.28)
        if count == 2:
            return tint(PALETTE["cyan"], 0.52)
        if count == 3:
            return tint(PALETTE["yellow"], 0.45)
        return tint(PALETTE["orange"], 0.62)

    # -- interaction -------------------------------------------------------
    def mouseMoveEvent(self, event) -> None:
        position = event.position()
        for rect, band, channel, count in self._cells:
            if rect.adjusted(-1, -1, 1, 1).contains(position):
                freq = channels.channel_to_freq(band, channel)
                if count:
                    note = f"{count} network{'s' if count != 1 else ''} observed on this channel"
                else:
                    note = "no networks observed on this channel"
                QToolTip.showText(event.globalPosition().toPoint(), f"Channel {channel} \u2022 {freq} MHz\n{note}", self)
                return
        QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        position = event.position()
        for rect, band, _channel, _count in self._cells:
            if rect.contains(position):
                self.band_clicked.emit(band.key)
                return
        super().mouseReleaseEvent(event)
