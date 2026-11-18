"""Signal-strength time-series chart for the Signal Monitor page."""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ...core.constants import PALETTE
from ..theme import font
from .base import tint

pg.setConfigOptions(antialias=True, useOpenGL=False)


class SignalChart(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("#08141F")
        self.plot.setStyleSheet("border: none;")
        layout.addWidget(self.plot)

        item = self.plot.getPlotItem()
        item.setMenuEnabled(False)
        item.hideButtons()
        item.showGrid(x=True, y=True, alpha=0.15)
        item.setMouseEnabled(x=False, y=False)
        item.getViewBox().setDefaultPadding(0)
        item.getAxis("left").setLabel("RSSI (dBm)", color=PALETTE["muted"], size="8pt")
        item.getAxis("bottom").setLabel("SECONDS AGO", color=PALETTE["muted"], size="8pt")
        for name in ("left", "bottom"):
            axis = item.getAxis(name)
            axis.setPen(pg.mkPen("#17465B", width=1))
            axis.setTextPen(pg.mkPen("#647F91"))
            axis.setStyle(tickFont=font(8), tickLength=-4, tickTextOffset=6)

        self.curve = pg.PlotDataItem(pen=pg.mkPen(PALETTE["cyan"], width=1.9))
        self.plot.addItem(self.curve)

        self.dots = pg.ScatterPlotItem(size=4, pen=pg.mkPen(None), brush=pg.mkBrush(PALETTE["cyan"]))
        self.plot.addItem(self.dots)

        self.average = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen(PALETTE["yellow"], width=1, style=Qt.PenStyle.DashLine),
        )
        self.average.setVisible(False)
        self.plot.addItem(self.average)

        self.empty = QLabel("No tracked network \u2014 pick one from the list to begin")
        self.empty.setFont(font(10))
        self.empty.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.empty.setParent(self.plot)
        self.empty.show()

        self.setMinimumHeight(200)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.empty.setGeometry(0, 0, self.width(), self.height())

    def clear(self) -> None:
        self.curve.setData([], [])
        self.dots.setData([], [])
        self.average.setVisible(False)
        self.empty.show()

    def set_series(self, series: list[tuple[float, int]], color: str, window_s: int) -> None:
        if len(series) < 2:
            self.clear()
            if series:
                self.empty.setText("Collecting samples\u2026 one more scan is needed")
            else:
                self.empty.setText("No tracked network \u2014 pick one from the list to begin")
            return
        self.empty.hide()
        now = series[-1][0]
        cutoff = now - max(30, window_s)
        visible = [point for point in series if point[0] >= cutoff] or series
        xs = [ts - now for ts, _ in visible]
        ys = [rssi for _, rssi in visible]
        self.curve.setData(xs, ys, fillLevel=-100.0, brush=tint(color, 0.12))
        self.curve.setPen(pg.mkPen(color, width=1.9))
        self.dots.setData(xs, ys, brush=pg.mkBrush(color))
        average = sum(ys) / len(ys)
        self.average.setValue(average)
        self.average.setPen(pg.mkPen(PALETTE["yellow"], width=1, style=Qt.PenStyle.DashLine))
        self.average.setVisible(True)
        # Fit the samples that exist, with a little breathing room, instead of
        # parking a short trace against the right edge of a 30-minute axis.
        span = max(10.0, (xs[-1] - xs[0]) * 1.15)
        self.plot.setXRange(-span - 1.0, 1.0, padding=0)
        self.plot.setYRange(-100, -20, padding=0)
