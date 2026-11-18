"""Live spectrum graph.

Renders channel-shaped curves from observed access-point data (channel, width,
RSSI) with hover inspection, crosshair readout, zoom, pan and automatic
scaling. A separate mode renders real FFT power when SDR hardware is present.
"""

from __future__ import annotations

import math

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ...core import channels
from ...core.constants import GRAPH_FLOOR_DBM, PALETTE
from ...core.models import AccessPoint, Band
from ...services.spectrum_service import assign_colors, build_curve, shape
from ..theme import font, mono_family
from .base import rgba, tint

pg.setConfigOptions(antialias=True, useOpenGL=False)
pg.setConfigOption("background", "#08141F")
pg.setConfigOption("foreground", "#647F91")


class HoverCard(QFrame):
    """Floating inspection card shown while hovering a curve."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("HoverCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            f"QFrame#HoverCard {{ background: rgba(9, 23, 37, 0.97); border: 1px solid {rgba(PALETTE['cyan'], 0.55)};"
            f" border-radius: 10px; }}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 9, 12, 10)
        outer.setSpacing(5)

        head = QHBoxLayout()
        head.setSpacing(7)
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.name = QLabel("--")
        self.name.setFont(font(11.5, 600))
        self.name.setStyleSheet(f"color: {PALETTE['text']};")
        head.addWidget(self.dot)
        head.addWidget(self.name)
        head.addStretch(1)
        self.badge = QLabel("")
        self.badge.setFont(font(8.5, 600, 0.7))
        self.badge.setStyleSheet(
            f"color: {PALETTE['cyan']}; background: rgba(0,217,245,0.10); border-radius: 5px; padding: 1px 5px;"
        )
        head.addWidget(self.badge)
        outer.addLayout(head)

        self.bssid = QLabel("--")
        self.bssid.setFont(QFont(mono_family(), 8))
        self.bssid.setStyleSheet(f"color: {PALETTE['muted']};")
        outer.addWidget(self.bssid)

        grid = QHBoxLayout()
        grid.setSpacing(16)
        col1 = QVBoxLayout()
        col1.setSpacing(2)
        col2 = QVBoxLayout()
        col2.setSpacing(2)
        self._rows: dict[str, QLabel] = {}
        for key, target in (("Channel", col1), ("Center", col1), ("Width", col1),
                            ("Signal", col2), ("Security", col2), ("Vendor", col2)):
            row = QHBoxLayout()
            row.setSpacing(6)
            caption = QLabel(key.upper())
            caption.setFont(font(7.5, 600, 0.8))
            caption.setStyleSheet(f"color: {PALETTE['muted']};")
            value = QLabel("--")
            value.setFont(font(9, 500))
            value.setStyleSheet(f"color: {PALETTE['text_secondary']};")
            row.addWidget(caption)
            row.addWidget(value)
            target.addLayout(row)
            self._rows[key] = value
        grid.addLayout(col1)
        grid.addLayout(col2)
        outer.addLayout(grid)
        self.setVisible(False)

    def update_ap(self, ap: AccessPoint, color: str) -> None:
        self.dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
        self.name.setText(ap.display_ssid)
        self.badge.setText(ap.band.label)
        self.bssid.setText(ap.bssid.upper())
        self._rows["Channel"].setText(str(ap.channel))
        self._rows["Center"].setText(f"{ap.frequency_mhz} MHz")
        self._rows["Width"].setText(f"{ap.width_mhz} MHz")
        signal = self._rows["Signal"]
        signal.setText(f"{ap.rssi} dBm")
        from ...core.constants import rssi_color

        signal.setStyleSheet(f"color: {rssi_color(ap.rssi)}; font-weight: 600;")
        self._rows["Security"].setText(ap.security)
        self._rows["Vendor"].setText(ap.vendor[:22])
        self.adjustSize()


class SpectrumPlot(QWidget):
    network_selected = Signal(str)

    def __init__(self, band: Band = Band.GHZ_24, parent: QWidget | None = None):
        super().__init__(parent)
        self._band = band
        self._floor = GRAPH_FLOOR_DBM
        self._mode = "wifi"
        self._aps: dict[str, AccessPoint] = {}
        self._colors: dict[str, str] = {}
        self._items: dict[str, pg.PlotDataItem] = {}
        self._labels: dict[str, pg.TextItem] = {}
        self._shapes: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._target: dict[str, float] = {}
        self._current: dict[str, float] = {}
        self._hovered: str | None = None
        self._auto_y = True
        self._last_envelope: tuple[np.ndarray, np.ndarray] | None = None
        self._label_pool: list[pg.TextItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("#08141F")
        self.plot.setStyleSheet("border: none;")
        self.plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.plot)

        item = self.plot.getPlotItem()
        item.setMenuEnabled(False)
        item.hideButtons()
        item.showGrid(x=True, y=True, alpha=0.16)
        item.setMouseEnabled(x=True, y=False)
        item.getViewBox().setDefaultPadding(0)
        item.getViewBox().setMouseMode(pg.ViewBox.RectMode)
        item.getViewBox().setBorder(pg.mkPen(None))

        for axis_name in ("left", "bottom"):
            axis = item.getAxis(axis_name)
            axis.setPen(pg.mkPen("#17465B", width=1))
            axis.setTextPen(pg.mkPen("#647F91"))
            axis.setStyle(tickFont=font(8.5), tickLength=-4, tickTextOffset=6)
        item.getAxis("left").setLabel("SIGNAL (dBm)", color=PALETTE["muted"], size="8pt")
        item.getAxis("bottom").setLabel("FREQUENCY (MHz)", color=PALETTE["muted"], size="8pt")

        # crosshair
        self.vline = pg.InfiniteLine(angle=90, movable=False,
                                     pen=pg.mkPen(PALETTE["cyan"], width=1, style=Qt.PenStyle.DashLine))
        self.hline = pg.InfiniteLine(angle=0, movable=False,
                                     pen=pg.mkPen(PALETTE["cyan"], width=1, style=Qt.PenStyle.DashLine))
        self.vline.setZValue(50)
        self.hline.setZValue(50)
        self.plot.addItem(self.vline, ignoreBounds=True)
        self.plot.addItem(self.hline, ignoreBounds=True)
        self.vline.setVisible(False)
        self.hline.setVisible(False)

        # labels / badges (overlay children, not scene items)
        self.badge = QLabel("WI-FI CHANNEL VISUALISATION", self)
        self.badge.setFont(font(7.5, 600, 1.0))
        self.badge.setStyleSheet(
            f"color: {PALETTE['cyan']}; background: rgba(0, 217, 245, 0.09);"
            f" border: 1px solid rgba(0, 217, 245, 0.28); border-radius: 6px; padding: 2px 7px;"
        )
        self.badge.setVisible(False)

        self.readout = QLabel("", self)
        self.readout.setFont(font(8.5, 500, 0.4))
        self.readout.setStyleSheet(f"color: {PALETTE['text_secondary']}; background: transparent;")
        self.readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.hint = QLabel("SCROLL TO ZOOM  \u2022  DRAG TO PAN  \u2022  DOUBLE-CLICK TO RESET", self)
        self.hint.setFont(font(7.5, 500, 0.6))
        self.hint.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")

        self.hover = HoverCard(self)

        self._cursor_ap: str | None = None
        self._mouse_scene = None

        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)
        item.getViewBox().sigRangeChanged.connect(lambda *_: self._reposition_labels())
        self.plot.scene().sigMouseClicked.connect(self._on_scene_clicked)

        self._anim = QTimer(self)
        self._anim.setInterval(33)
        self._anim.timeout.connect(self._animate)

        self.set_band(band)

    # -- public API --------------------------------------------------------
    @property
    def band(self) -> Band:
        return self._band

    def set_band(self, band: Band) -> None:
        self._band = band
        self._clear_items()
        lo, hi = channels.band_bounds(band)
        self.plot.setXRange(lo, hi, padding=0.01)
        self.plot.setLimits(xMin=lo, xMax=hi, yMin=-110, yMax=-5)
        self._set_ticks(band)
        self.badge.setText("FFT MEASUREMENT" if self._mode == "fft" else "WI-FI CHANNEL VISUALISATION")

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.badge.setText("FFT MEASUREMENT \u2022 SDR" if mode == "fft" else "WI-FI CHANNEL VISUALISATION")
        self.badge.setVisible(mode == "fft")
        if mode == "wifi" and self._last_envelope is not None:
            self._clear_items()

    def set_auto_y(self, enabled: bool) -> None:
        self._auto_y = enabled

    def set_data(self, aps: list[AccessPoint], band: Band | None = None) -> None:
        if band is not None and band is not self._band:
            self.set_band(band)
        band = self._band
        in_band = [ap for ap in aps if ap.band is band]
        self._aps = {ap.bssid: ap for ap in in_band}
        self._colors = assign_colors(in_band)
        active = set(self._aps)
        self.readout.setText("")

        for bssid in list(self._items):
            if bssid not in active:
                self.plot.removeItem(self._items.pop(bssid))
                self._labels.pop(bssid, None)
                self._shapes.pop(bssid, None)
                self._target.pop(bssid, None)
                self._current.pop(bssid, None)

        for ap in in_band:
            curve = build_curve(ap, self._colors[ap.bssid], self._floor)
            self._shapes[ap.bssid] = (curve.x, shape(curve.x, ap.frequency_mhz, ap.width_mhz))
            self._target[ap.bssid] = float(ap.rssi)
            if ap.bssid not in self._current:
                self._current[ap.bssid] = float(ap.rssi) - 12.0 if self._items else float(ap.rssi)

            item = self._items.get(ap.bssid)
            if item is None:
                color = self._colors[ap.bssid]
                item = pg.PlotDataItem(
                    curve.x,
                    self._y_for(ap.bssid),
                    pen=pg.mkPen(color, width=1.9),
                    fillLevel=self._floor,
                    brush=pg.mkBrush(tint(color, 0.05)),
                )
                item.setZValue(10 + min(40, max(0, 60 + ap.rssi)))
                self.plot.addItem(item)
                self._items[ap.bssid] = item
            else:
                item.setData(curve.x, self._y_for(ap.bssid))

        self._ensure_labels()
        if self._auto_y and in_band:
            top = max(ap.rssi for ap in in_band)
            # Leave headroom above the strongest network and keep the upper
            # bound off the 5 dB tick grid so the top label is never clipped.
            upper = 5 * math.ceil((top + 8) / 5.0) + 4
            upper = min(-12.0, max(-50.0, upper))
            self.plot.setYRange(-100, upper, padding=0)
        if not self._anim.isActive():
            self._anim.start()
        self._reposition_labels()

    def set_fft_frame(self, frequencies: np.ndarray, power_db: np.ndarray, band: Band | None = None) -> None:
        if band is not None and band is not self._band:
            self.set_band(band)
        self._mode = "fft"
        self.badge.setText("FFT MEASUREMENT \u2022 SDR")
        self.badge.setVisible(True)
        if "fft" not in self._items:
            self._clear_items()
            item = pg.PlotDataItem(
                pen=pg.mkPen(PALETTE["cyan"], width=1.6),
                fillLevel=-110,
                brush=pg.mkBrush(tint(PALETTE["cyan"], 0.14)),
            )
            self.plot.addItem(item)
            self._items["fft"] = item
        self._items["fft"].setData(frequencies, power_db)

    def clear(self) -> None:
        self._clear_items()
        self.hover.setVisible(False)
        self.readout.setText("NO DATA")

    # -- internals ---------------------------------------------------------
    def _clear_items(self) -> None:
        for item in self._items.values():
            self.plot.removeItem(item)
        for text in self._labels.values():
            self.plot.removeItem(text)
        self._items.clear()
        self._labels.clear()
        self._shapes.clear()
        self._target.clear()
        self._current.clear()
        self._aps.clear()

    def _y_for(self, bssid: str) -> np.ndarray:
        xs, shp = self._shapes[bssid]
        level = self._current.get(bssid, self._target.get(bssid, -100))
        return self._floor + max(1.0, level - self._floor) * shp

    def _set_ticks(self, band: Band) -> None:
        lo, hi = channels.band_bounds(band)
        if band is Band.GHZ_24:
            major = list(range(2400, 2501, 20))
            minor = list(range(2400, 2501, 5))
        elif band is Band.GHZ_5:
            major = list(range(5150, 5926, 200))
            minor = list(range(5150, 5926, 20))
        else:
            major = list(range(5950, 7126, 200))
            minor = list(range(5950, 7126, 20))
        major_ticks = [(float(v), str(v)) for v in major if lo <= v <= hi]
        minor_ticks = [(float(v), "") for v in minor if lo <= v <= hi]
        self.plot.getPlotItem().getAxis("bottom").setTicks([major_ticks, minor_ticks])
        self.plot.getPlotItem().getAxis("left").setTicks(
            [[(float(v), str(v)) for v in range(-100, -19, 10)], []]
        )

    def _ensure_labels(self) -> None:
        for bssid, ap in self._aps.items():
            text = self._labels.get(bssid)
            if text is None:
                text = pg.TextItem(anchor=(0.5, 1.0))
                text.setZValue(80)
                self.plot.addItem(text)
                self._labels[bssid] = text
            color = self._colors.get(bssid, PALETTE["cyan"])
            short = ap.display_ssid if len(ap.display_ssid) <= 16 else ap.display_ssid[:15] + "\u2026"
            text.setText(short)
            text.setColor(color)
            text.textItem.setFont(font(8, 500))
            text.setPos(ap.frequency_mhz, min(-16.0, ap.rssi + 2.2))

    def _reposition_labels(self) -> None:
        if not self._labels or not self._aps:
            return
        view_range = self.plot.getPlotItem().getViewBox().viewRange()
        xmin, xmax = view_range[0]
        vb_width = max(1, self.plot.getPlotItem().getViewBox().width())
        units_per_px = (xmax - xmin) / vb_width
        fm = self.fontMetrics()
        placed: list[tuple[float, float]] = []
        visible = [(ap, self._labels.get(bssid)) for bssid, ap in self._aps.items() if bssid in self._labels]
        visible.sort(key=lambda pair: pair[0].rssi, reverse=True)
        for ap, text in visible:
            if text is None:
                continue
            width = fm.horizontalAdvance(ap.display_ssid) * 0.72 + 10
            half = width * units_per_px * 0.5
            lo, hi = ap.frequency_mhz - half, ap.frequency_mhz + half
            if hi < xmin or lo > xmax:
                text.setVisible(False)
                continue
            collision = False
            for plo, phi in placed:
                if lo < phi and hi > plo:
                    collision = True
                    break
            if collision:
                text.setVisible(False)
                continue
            text.setVisible(True)
            placed.append((lo, hi))
            text.setPos(ap.frequency_mhz, min(-16.5, ap.rssi + 2.4))

    def _animate(self) -> None:
        moved = False
        for bssid, target in self._target.items():
            current = self._current.get(bssid, target)
            if abs(target - current) > 0.12:
                self._current[bssid] = current + (target - current) * 0.28
                moved = True
            else:
                self._current[bssid] = target
            item = self._items.get(bssid)
            if item is not None:
                item.setData(self._shapes[bssid][0], self._y_for(bssid))
        if not moved and not self._hovered:
            self._anim.stop()

    def _on_mouse_moved(self, pos) -> None:
        if not self._items or not self._aps:
            return
        vb = self.plot.getPlotItem().getViewBox()
        if not self.plot.sceneBoundingRect().contains(pos):
            self.hover.setVisible(False)
            return
        point = vb.mapSceneToView(pos)
        x, y = point.x(), point.y()
        self._mouse_scene = QPointF(pos)
        self.vline.setPos(x)
        self.hline.setPos(y)
        self.vline.setVisible(True)
        self.hline.setVisible(True)

        level = self._level_at(x)
        self.readout.setText(f"{x:.0f} MHz      {level:.0f} dBm")

        bssid = self._nearest_ap(x, y)
        self._set_hovered(bssid)
        if bssid:
            ap = self._aps[bssid]
            self.hover.update_ap(ap, self._colors.get(bssid, PALETTE["cyan"]))
            self._place_hover(pos)
            self.hover.setVisible(True)
        else:
            self.hover.setVisible(False)

    def _level_at(self, x: float) -> float:
        best = self._floor
        for bssid, (xs, shp) in self._shapes.items():
            if xs[0] <= x <= xs[-1]:
                idx = int(np.clip(np.searchsorted(xs, x), 0, len(xs) - 1))
                level = self._current.get(bssid, self._target.get(bssid, -100))
                best = max(best, self._floor + (level - self._floor) * shp[idx])
        return best

    def _nearest_ap(self, x: float, y: float) -> str | None:
        best_id = None
        best_score = 1e9
        for bssid, ap in self._aps.items():
            span = max(14.0, ap.width_mhz / 2.0)
            if abs(x - ap.frequency_mhz) > span:
                continue
            curve_y = self._level_at_point(bssid, x)
            if curve_y is None:
                continue
            score = abs(curve_y - y)
            if score < best_score:
                best_score = score
                best_id = bssid
        if best_id is not None and best_score <= 26:
            return best_id
        # fall back to the closest centre frequency
        nearest = min(self._aps.items(), key=lambda kv: abs(kv[1].frequency_mhz - x), default=None)
        if nearest and abs(nearest[1].frequency_mhz - x) < max(12.0, nearest[1].width_mhz / 2.0):
            return nearest[0]
        return None

    def _level_at_point(self, bssid: str, x: float) -> float | None:
        xs, shp = self._shapes[bssid]
        if not (xs[0] <= x <= xs[-1]):
            return None
        idx = int(np.clip(np.searchsorted(xs, x), 0, len(xs) - 1))
        level = self._current.get(bssid, self._target.get(bssid, -100))
        return self._floor + (level - self._floor) * shp[idx]

    def _set_hovered(self, bssid: str | None) -> None:
        if bssid == self._hovered:
            return
        self._hovered = bssid
        for key, item in self._items.items():
            if key == "fft":
                continue
            color = self._colors.get(key, PALETTE["cyan"])
            if key == bssid:
                item.setPen(pg.mkPen(color, width=2.6))
                item.setBrush(pg.mkBrush(tint(color, 0.24)))
            else:
                item.setPen(pg.mkPen(color, width=1.7))
                item.setBrush(pg.mkBrush(tint(color, 0.11)))
        self.update()

    def _place_hover(self, pos: QPointF) -> None:
        margin = 14
        self.hover.adjustSize()
        w, h = self.hover.width(), self.hover.height()
        x = int(pos.x() + 18)
        y = int(pos.y() - h - 14)
        if x + w + margin > self.width():
            x = int(pos.x() - w - 18)
        if y < margin:
            y = int(pos.y() + 20)
        if y + h + margin > self.height():
            y = max(margin, self.height() - h - margin)
        self.hover.move(max(margin, x), max(margin, y))
        self.hover.raise_()

    def _on_scene_clicked(self, event) -> None:
        if self._hovered and event.button() == Qt.MouseButton.LeftButton:
            self.network_selected.emit(self._hovered)

    # -- painting overlays --------------------------------------------------
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.badge.adjustSize()
        self.badge.move(12, 10)
        self.readout.adjustSize()
        self.readout.move(max(12, self.width() - self.readout.width() - 14), 10)
        self.hint.adjustSize()
        self.hint.move(12, max(0, self.height() - self.hint.height() - 6))
        self._reposition_labels()

    def leaveEvent(self, event) -> None:
        self.vline.setVisible(False)
        self.hline.setVisible(False)
        self.hover.setVisible(False)
        self.readout.setText("")
        self._set_hovered(None)
        super().leaveEvent(event)
