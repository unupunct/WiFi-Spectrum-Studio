"""Per-band overview: network counts, density estimate and busiest channels."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ...core import channels
from ...core.constants import PALETTE
from ...core.models import Band, ScanSnapshot
from ..theme import font
from .base import tint


class BandOverview(QWidget):
    """Three compact lanes (2.4 / 5 / 6 GHz) drawn from observed scans."""

    ROW_HEIGHT = 52

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._bands: list[tuple[Band, int, float, list[int]]] = []
        self.setMinimumHeight(self.ROW_HEIGHT * 3 + 2)
        self.set_bands(None)

    def set_bands(self, snapshot: ScanSnapshot | None) -> None:
        rows: list[tuple[Band, int, float, list[int]]] = []
        for band in Band.all():
            aps = snapshot.by_band(band) if snapshot else []
            counts = snapshot.counts_by_channel(band) if snapshot else {}
            top = [ch for ch, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:3]]
            rows.append((band, len(aps), channels.congestion_pct(aps, band), top))
        self._bands = rows
        self.update()

    def paintEvent(self, event) -> None:
        if not self._bands:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = self.width()
        row_h = self.height() / 3.0

        for index, (band, count, density, top) in enumerate(self._bands):
            top_y = index * row_h
            mid = top_y + row_h / 2

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(band.color))
            painter.drawEllipse(QPointF(4, mid - 4), 3.2, 3.2)

            painter.setFont(font(10.5, 600, 0.2))
            painter.setPen(QColor(PALETTE["text"]))
            painter.drawText(QPointF(15, mid + 1), band.label)

            total = len(channels.band_channels(band))
            painter.setFont(font(7.5, 500, 0.5))
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(QPointF(15, mid + 14), f"{total} channels")

            painter.setFont(font(17, 600, 0.2))
            painter.setPen(QColor(PALETTE["text"] if count else PALETTE["muted"]))
            painter.drawText(QPointF(84, mid + 2), str(count))
            offset = painter.fontMetrics().horizontalAdvance(str(count))
            painter.setFont(font(7.5, 600, 0.7))
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(QPointF(88 + offset, mid + 1), "APS")

            bar_rect = QRectF(140, mid - 3, max(20, width - 220), 6)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#0A1B29"))
            painter.drawRoundedRect(bar_rect, 3, 3)
            if density > 0.4:
                fill = QRectF(bar_rect.left(), bar_rect.top(), bar_rect.width() * density / 100.0, 6)
                color = PALETTE["green"] if density < 25 else PALETTE["yellow"] if density < 50 else PALETTE["orange"] if density < 75 else PALETTE["red"]
                grad = QLinearGradient(fill.left(), 0, fill.right(), 0)
                grad.setColorAt(0.0, tint(color, 0.45))
                grad.setColorAt(1.0, tint(color, 0.95))
                painter.setBrush(grad)
                painter.drawRoundedRect(fill, 3, 3)

            label = (
                "  ".join(f"ch {ch}" for ch in top) if top else "no observations in this band"
            )
            painter.setFont(font(7.5, 500, 0.4))
            painter.setPen(QColor(tint(PALETTE["muted"], 0.9)))
            painter.drawText(
                QRectF(140, mid + 8, max(20, width - 220), 12),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

            painter.setFont(font(11, 600, 0.2))
            painter.setPen(QColor(PALETTE["text_secondary"] if count else PALETTE["muted"]))
            painter.drawText(
                QRectF(width - 72, mid - 10, 68, 14),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{density:.0f}%",
            )
            painter.setFont(font(7.5, 500, 0.5))
            painter.setPen(QColor(PALETTE["muted"]))
            painter.drawText(
                QRectF(width - 72, mid + 3, 68, 12),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "band density",
            )

            if index < len(self._bands) - 1:
                painter.setPen(QPen(QColor(tint(PALETTE["border"], 0.45)), 1))
                y = top_y + row_h
                painter.drawLine(QPointF(0, y), QPointF(width, y))
        painter.end()
