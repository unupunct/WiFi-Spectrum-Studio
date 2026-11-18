"""Waterfall (spectrogram) view.

Wi-Fi mode: one row per scan, built from observed access points.
SDR mode: one row per FFT capture. The widget never claims RF measurement for
scan-derived rows - the page header carries the data-source badge.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ...core import channels
from ...core.constants import PALETTE
from ...core.models import AccessPoint, Band
from ...services.waterfall_service import WaterfallService
from ..theme import font
from .base import tint


class WaterfallView(QWidget):
    state_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        self.service = WaterfallService(rows=180, bins=640)
        self._band = Band.GHZ_24
        self._mode = "wifi"
        self._state = "stopped"
        self._offset = 0.0
        self._rows_per_second = 0.5
        self._last_push = 0.0
        self._zoom = 1
        self._pan = 0.5
        self._hover_x: float | None = None
        self._img: QImage | None = None
        self._img_data = None
        self._dirty = True
        self._drag_from: QPointF | None = None
        self._drag_pan = 0.5

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # -- state -------------------------------------------------------------
    @property
    def state(self) -> str:
        return self._state

    def _set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self.state_changed.emit(state)
            self.update()

    def start(self) -> None:
        self._set_state("running")

    def pause(self) -> None:
        if self._state == "running":
            self._set_state("paused")

    def resume(self) -> None:
        if self._state in ("paused", "stopped"):
            self._set_state("running")

    def stop(self) -> None:
        self._set_state("stopped")

    def clear(self) -> None:
        self.service.reset()
        self._dirty = True
        self.update()

    def set_palette(self, name: str) -> None:
        self.service.set_palette(name)
        self._dirty = True
        self.update()

    def set_band(self, band: Band) -> None:
        if band is not self._band:
            self._band = band
            self.clear()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.update()

    def set_zoom(self, factor: int) -> None:
        self._zoom = max(1, min(8, factor))
        self._pan = 0.5
        self.update()

    @property
    def zoom(self) -> int:
        return self._zoom

    # -- data --------------------------------------------------------------
    def feed(self, aps: list[AccessPoint], band: Band) -> None:
        if self._state != "running":
            return
        self.set_band(band)
        row = self.service.row_from_aps(aps, band)
        self._push(row)

    def feed_fft(self, frame, band: Band) -> None:
        if self._state != "running" or frame is None:
            return
        self.set_band(band)
        row = self.service.row_from_fft(
            frame.power_db,
            float(frame.frequencies[0]),
            float(frame.frequencies[-1]),
            band,
        )
        self._push(row)

    def _push(self, row: np.ndarray) -> None:
        import time

        now = time.time()
        if self._last_push:
            delta = max(0.05, now - self._last_push)
            self._rows_per_second = 0.7 * self._rows_per_second + 0.3 * (1.0 / delta)
        self._last_push = now
        self.service.push_row(row)
        self._offset = 0.0
        self._dirty = True
        self.update()

    # -- painting ----------------------------------------------------------
    def _tick(self) -> None:
        if self._state == "running" and self._last_push:
            import time

            elapsed = time.time() - self._last_push
            self._offset = min(1.0, elapsed * self._rows_per_second)
            self._dirty = True
        if self._dirty and self.isVisible():
            self.update()

    def _build_image(self) -> None:
        rgb = self.service.rgb()
        self._img_data = np.ascontiguousarray(rgb)
        h, w, _ = self._img_data.shape
        self._img = QImage(self._img_data.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self._dirty = False

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        legend_w = 44
        axis_h = 18
        plot = QRectF(0, 0, max(10, w - legend_w), max(10, h - axis_h))

        painter.fillRect(self.rect(), QColor("#061019"))

        if self._dirty or self._img is None:
            self._build_image()

        if self._img is not None and plot.width() > 4:
            row_h = plot.height() / self.service.rows
            offset_px = self._offset * row_h if self._state == "running" else 0.0
            painter.save()
            painter.setClipRect(plot)
            target = QRectF(plot.left(), plot.top() + offset_px, plot.width(), plot.height())
            painter.drawImage(target, self._img)
            if offset_px > 0.5:
                gap = QRectF(plot.left(), plot.top(), plot.width(), offset_px)
                painter.drawImage(gap, self._img, QRectF(0, 0, self._img.width(), 1))
            painter.restore()

            # subtle grid
            pen = QPen(tint(PALETTE["blue"], 0.10))
            pen.setWidthF(1.0)
            painter.setPen(pen)
            lo, hi = channels.band_bounds(self._band)
            for value in self._major_ticks():
                x = plot.left() + plot.width() * (value - lo) / (hi - lo)
                painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))

            border = QPen(QColor("#123246"))
            border.setWidthF(1.0)
            painter.setPen(border)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(plot.adjusted(0.5, 0.5, -0.5, -0.5))

            # "now" marker
            painter.setPen(tint(PALETTE["cyan"], 0.55))
            painter.drawLine(QPointF(plot.left(), plot.top() + 1), QPointF(plot.right(), plot.top() + 1))

        self._draw_legend(painter, QRectF(w - legend_w, 0, legend_w, h))
        self._draw_axis(painter, plot)

        if self._hover_x is not None and plot.width() > 10:
            painter.setPen(QPen(tint(PALETTE["cyan"], 0.5), 1, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(self._hover_x, plot.top()), QPointF(self._hover_x, plot.bottom()))

        if self._state == "paused":
            self._draw_state_tag(painter, plot, "PAUSED", PALETTE["yellow"])
        elif self._state == "stopped":
            self._draw_state_tag(painter, plot, "STOPPED", PALETTE["muted"])
        painter.end()

    def _draw_state_tag(self, painter: QPainter, plot: QRectF, text: str, color: str) -> None:
        painter.setFont(font(8, 600, 1.0))
        fm = painter.fontMetrics()
        width = fm.horizontalAdvance(text) + 14
        rect = QRectF(plot.center().x() - width / 2, plot.top() + 9, width, 17)
        painter.setBrush(tint("#04121F", 0.82))
        painter.setPen(QPen(tint(color, 0.55), 1))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QColor(color))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _major_ticks(self) -> list[float]:
        lo, hi = channels.band_bounds(self._band)
        if self._band is Band.GHZ_24:
            return [float(v) for v in range(2400, 2501, 20)]
        if self._band is Band.GHZ_5:
            return [float(v) for v in range(5200, 5900, 200)]
        return [float(v) for v in range(6000, 7100, 200)]

    def _draw_axis(self, painter: QPainter, plot: QRectF) -> None:
        painter.setFont(font(8, 500, 0.35))
        painter.setPen(tint(PALETTE["text_secondary"], 0.92))
        lo, hi = channels.band_bounds(self._band)
        baseline = self.height() - 3.0
        for value in self._major_ticks():
            x = plot.left() + plot.width() * (value - lo) / (hi - lo)
            painter.drawLine(QPointF(x, plot.bottom()), QPointF(x, plot.bottom() + 3))
            text = f"{int(value)}"
            width = painter.fontMetrics().horizontalAdvance(text)
            text_x = max(plot.left() + 1.0, min(plot.right() - width - 1.0, x - width / 2))
            painter.drawText(QPointF(text_x, baseline), text)

        # "now" tag: the newest row sits at the top of the waterfall
        painter.setFont(font(7, 600, 0.8))
        tag = QRectF(plot.right() - 44, plot.top() + 4, 38, 14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(tint("#04121F", 0.72))
        painter.drawRoundedRect(tag, 4, 4)
        painter.setPen(tint(PALETTE["cyan"], 0.9))
        painter.drawText(tag, Qt.AlignmentFlag.AlignCenter, "NOW")

    def _draw_legend(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(font(7, 500, 0.6))
        painter.setPen(QColor(PALETTE["muted"]))
        bar = QRectF(rect.left() + 6, 14, 8, max(24, rect.height() - 40))
        lut = self.service._lut  # noqa: SLF001 - intentional read of display LUT
        grad = QLinearGradient(bar.topLeft(), bar.bottomLeft())
        for index in range(0, 256, 16):
            r, g, b = lut[index]
            grad.setColorAt(index / 255.0, QColor(int(r), int(g), int(b)))
        r, g, b = lut[255]
        grad.setColorAt(1.0, QColor(int(r), int(g), int(b)))
        painter.setPen(QPen(tint(PALETTE["border"], 0.9), 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(bar, 2, 2)
        painter.setPen(QColor(PALETTE["muted"]))
        painter.drawText(QRectF(bar.right() + 4, bar.top() - 3, 28, 10), Qt.AlignmentFlag.AlignLeft, "HIGH")
        painter.drawText(QRectF(bar.right() + 4, bar.bottom() - 7, 28, 10), Qt.AlignmentFlag.AlignLeft, "LOW")

        painter.save()
        painter.translate(bar.right() + 14, bar.center().y())
        painter.rotate(-90)
        painter.setFont(font(6.5, 500, 1.2))
        painter.setPen(tint(PALETTE["muted"], 0.75))
        text = "FFT dBm" if self._mode == "fft" else "RELATIVE"
        width = painter.fontMetrics().horizontalAdvance(text)
        painter.drawText(QRectF(-width / 2, -5, width, 10), Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    # -- interaction -------------------------------------------------------
    def mouseMoveEvent(self, event) -> None:
        self._hover_x = event.position().x()
        if self._drag_from is not None and self._zoom > 1:
            delta = event.position().x() - self._drag_from.x()
            plot_w = max(10, self.width() - 44)
            self._pan = min(1.0, max(0.0, self._drag_pan - delta / plot_w / self._zoom))
        self.update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_from = event.position()
            self._drag_pan = self._pan
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_from = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_x = None
        self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event) -> None:
        if event.angleDelta().y() > 0:
            self.set_zoom(self._zoom * 2)
        else:
            self.set_zoom(max(1, self._zoom // 2))
        super().wheelEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(800, 120)
