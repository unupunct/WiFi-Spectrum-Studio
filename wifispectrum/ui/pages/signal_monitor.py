"""Signal Monitor: live RSSI history for the networks the user tracks."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import PALETTE, rssi_color
from ...core.events import bus
from ...core.models import ScanSnapshot
from .. import icons
from ..widgets.base import (
    Badge,
    IconButton,
    PageHeader,
    Panel,
    StatBlock,
    label,
    rgba,
)
from ..widgets.notice import NoticeBar
from ..widgets.signal_chart import SignalChart


class TrackedRow(QWidget):
    selected = Signal(str)
    removed = Signal(str)

    def __init__(self, bssid: str, ssid: str, channel: int, rssi: int | None,
                 active: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self._bssid = bssid
        self._active = active
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(46)

        row = QHBoxLayout(self)
        row.setContentsMargins(9, 4, 4, 4)
        row.setSpacing(7)

        self.dot = QWidget()
        self.dot.setFixedSize(7, 7)
        self.dot.setStyleSheet(f"background: {PALETTE['cyan'] if active else PALETTE['muted']}; border-radius: 3px;")
        row.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)
        self.name = label(ssid, 9.6, PALETTE["text"], 600, 0.05)
        self.meta = label(f"ch {channel} \u2022 {bssid[-8:].upper()}", 7.8, PALETTE["muted"], 500, 0.3)
        text.addWidget(self.name)
        text.addWidget(self.meta)
        row.addLayout(text, 1)

        self.value = label(f"{rssi} dBm" if rssi is not None else "\u2014", 9.6,
                           rssi_color(rssi) if rssi is not None else PALETTE["muted"], 600, 0.1)
        row.addWidget(self.value)

        self.remove = IconButton("close", "Stop tracking", 20, 10)
        self.remove.clicked.connect(lambda: self.removed.emit(self._bssid))
        row.addWidget(self.remove)

        self._apply_style()

    def _apply_style(self) -> None:
        if self._active:
            self.setStyleSheet(
                f"background: {rgba(PALETTE['cyan'], 0.08)}; border: 1px solid {rgba(PALETTE['cyan'], 0.32)};"
                " border-radius: 8px;"
            )
        else:
            self.setStyleSheet("background: transparent; border: 1px solid transparent; border-radius: 8px;")

    def set_active(self, active: bool) -> None:
        self._active = active
        self.dot.setStyleSheet(f"background: {PALETTE['cyan'] if active else PALETTE['muted']}; border-radius: 3px;")
        self._apply_style()

    def set_rssi(self, rssi: int | None) -> None:
        self.value.setText(f"{rssi} dBm" if rssi is not None else "\u2014")
        self.value.setStyleSheet(f"color: {rssi_color(rssi) if rssi is not None else PALETTE['muted']}; background: transparent;")

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self._bssid)
        super().mousePressEvent(event)


class SignalMonitorPage(QWidget):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._snapshot: ScanSnapshot | None = None
        self._active: str | None = None
        self._rows: dict[str, TrackedRow] = {}
        self._auto_tracked = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(9)

        header = PageHeader(
            "Signal Monitor",
            "Track individual networks over time and watch their RSSI stability",
        )
        self.export_button = QPushButton("  Export Log")
        self.export_button.setObjectName("Ghost")
        self.export_button.setIcon(icons.icon("download", PALETTE["text_secondary"], 14))
        self.export_button.setFixedHeight(28)
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_button.clicked.connect(self._export)
        header.add_action(self.export_button)

        self.clear_button = QPushButton("  Clear History")
        self.clear_button.setObjectName("Ghost")
        self.clear_button.setIcon(icons.icon("trash", PALETTE["text_secondary"], 13))
        self.clear_button.setFixedHeight(28)
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(self._clear)
        header.add_action(self.clear_button)
        root.addWidget(header)

        self.notice = NoticeBar()
        root.addWidget(self.notice)

        content = QHBoxLayout()
        content.setSpacing(9)

        # -- tracked list --------------------------------------------------
        self.list_panel = Panel("Tracked Networks", "SELECT TO CHART")
        self.list_badge = Badge("0", PALETTE["cyan"])
        self.list_panel.add_action(self.list_badge)

        add_row = QHBoxLayout()
        add_row.setSpacing(6)
        self.picker = QComboBox()
        self.picker.setFixedHeight(28)
        add_row.addWidget(self.picker, 1)
        self.track_button = QPushButton("Track")
        self.track_button.setObjectName("Primary")
        self.track_button.setFixedWidth(58)
        self.track_button.setFixedHeight(28)
        self.track_button.clicked.connect(self._track_picked)
        add_row.addWidget(self.track_button)
        self.body_add = QWidget()
        self.body_add.setLayout(add_row)
        self.body_add.setFixedHeight(30)
        self.list_panel.add(self.body_add)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent;")
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.rows = QVBoxLayout(self.container)
        self.rows.setContentsMargins(0, 0, 4, 0)
        self.rows.setSpacing(4)
        self.rows.addStretch(1)
        self.scroll.setWidget(self.container)
        self.list_panel.add(self.scroll, 1)

        self.list_hint = label(
            "Pick a network above, or click any network on Live Spectrum and choose Track.",
            8.2,
            PALETTE["muted"],
            400,
            0.2,
            wrap=True,
        )
        self.list_panel.add(self.list_hint)
        self.sample_note = label(
            "One sample per scan \u2022 history is held in memory and cleared on exit.",
            7.8,
            PALETTE["muted"],
            400,
            0.05,
            wrap=True,
        )
        self.list_panel.add(self.sample_note)
        content.addWidget(self.list_panel, 27)

        # -- chart ---------------------------------------------------------
        self.chart_panel = Panel("Signal History", "RSSI OVER THE LAST 30 MINUTES")
        self.chart_badge = Badge("NO SELECTION", PALETTE["muted"])
        self.chart_panel.add_action(self.chart_badge)
        self.chart = SignalChart()
        self.chart_panel.add(self.chart, 1)

        stats = QHBoxLayout()
        stats.setSpacing(18)
        self.stat_current = StatBlock("Current", "\u2014", PALETTE["cyan"])
        self.stat_average = StatBlock("Average", "\u2014", PALETTE["text"])
        self.stat_min = StatBlock("Minimum", "\u2014", PALETTE["orange"])
        self.stat_max = StatBlock("Maximum", "\u2014", PALETTE["green"])
        self.stat_stability = StatBlock("Stability", "\u2014", PALETTE["green"])
        self.stat_samples = StatBlock("Samples", "\u2014", PALETTE["muted"])
        for block in (
            self.stat_current,
            self.stat_average,
            self.stat_min,
            self.stat_max,
            self.stat_stability,
            self.stat_samples,
        ):
            stats.addWidget(block)
        stats.addStretch(1)
        self.chart_panel.add_layout(stats)
        content.addWidget(self.chart_panel, 73)
        root.addLayout(content, 1)

        ctx.monitor.snapshot_ready.connect(self.on_snapshot)
        ctx.signals.updated.connect(self._refresh_chart)
        ctx.settings.changed.connect(lambda key, value: self._refresh_chart() if key == "history_minutes" else None)
        self._refresh_chart()

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self._rebuild_rows()
        self._refresh_chart()

    def on_snapshot(self, snapshot: ScanSnapshot) -> None:
        self._snapshot = snapshot
        self._fill_picker()

        if not self.ctx.signals.tracked and not self._auto_tracked and snapshot.aps:
            strongest = max(snapshot.aps, key=lambda ap: ap.rssi)
            self.ctx.signals.track(strongest.bssid, strongest.display_ssid, strongest.channel)
            self._auto_tracked = True
            self._active = strongest.bssid
        self._rebuild_rows()
        self._refresh_chart()

    def track(self, bssid: str) -> None:
        snapshot = self._snapshot
        ap = next((a for a in snapshot.aps if a.bssid == bssid), None) if snapshot else None
        if ap is None:
            return
        self.ctx.signals.track(ap.bssid, ap.display_ssid, ap.channel)
        self._active = bssid
        self._rebuild_rows()
        self._refresh_chart()

    # ------------------------------------------------------------------
    def _fill_picker(self) -> None:
        snapshot = self._snapshot
        aps = sorted(snapshot.aps, key=lambda ap: ap.rssi, reverse=True)[:40] if snapshot else []
        current = self.picker.currentData()
        self.picker.blockSignals(True)
        self.picker.clear()
        for ap in aps:
            self.picker.addItem(f"{ap.display_ssid}  \u2022  {ap.rssi} dBm", ap.bssid)
        if current:
            index = self.picker.findData(current)
            if index >= 0:
                self.picker.setCurrentIndex(index)
        self.picker.blockSignals(False)
        self.picker.setEnabled(bool(aps))
        self.track_button.setEnabled(bool(aps))

    def _track_picked(self) -> None:
        bssid = self.picker.currentData()
        if not bssid:
            return
        self.track(bssid)

    def _rebuild_rows(self) -> None:
        tracked = self.ctx.signals.tracked
        while self.rows.count():
            item = self.rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows.clear()

        if self._active not in tracked:
            self._active = tracked[0] if tracked else None

        for bssid in tracked:
            ssid, channel = self.ctx.signals.meta(bssid)
            stats = self.ctx.signals.stats(bssid)
            row = TrackedRow(bssid, ssid, channel, stats.get("current"), bssid == self._active)
            row.selected.connect(self._select)
            row.removed.connect(self._untrack)
            self._rows[bssid] = row
            self.rows.addWidget(row)
        self.rows.addStretch(1)
        self.list_hint.setVisible(not tracked)
        self.list_badge.setText(str(len(tracked)))

    def _select(self, bssid: str) -> None:
        self._active = bssid
        for key, row in self._rows.items():
            row.set_active(key == bssid)
        self._refresh_chart()

    def _untrack(self, bssid: str) -> None:
        self.ctx.signals.untrack(bssid)
        if self._active == bssid:
            self._active = None
        self._rebuild_rows()
        self._refresh_chart()

    def _refresh_chart(self) -> None:
        tracked = self.ctx.signals.tracked
        if not tracked:
            self.chart.clear()
            self.chart_badge.setText("NO SELECTION")
            self.chart_badge.setStyleSheet(
                f"color: {PALETTE['muted']}; background: {rgba(PALETTE['muted'], 0.08)};"
                f" border: 1px solid {rgba(PALETTE['muted'], 0.30)}; border-radius: 7px; padding: 1px 7px;"
            )
            for block in (self.stat_current, self.stat_average, self.stat_min, self.stat_max, self.stat_stability, self.stat_samples):
                block.set_value("\u2014", PALETTE["muted"])
            return
        bssid = self._active or tracked[0]
        series = self.ctx.signals.history(bssid)
        stats = self.ctx.signals.stats(bssid)
        ssid, channel = self.ctx.signals.meta(bssid)
        window = int(self.ctx.settings.get("history_minutes", 30)) * 60
        color = PALETTE["cyan"]
        self.chart.set_series(series, color, window)
        self.chart_badge.setText(f"{ssid[:18]} \u2022 CH {channel}")
        self.chart_badge.setStyleSheet(
            f"color: {PALETTE['cyan']}; background: {rgba(PALETTE['cyan'], 0.10)};"
            f" border: 1px solid {rgba(PALETTE['cyan'], 0.32)}; border-radius: 7px; padding: 1px 7px;"
        )
        self.chart_panel.set_hint(f"RSSI HISTORY \u2022 LAST {max(1, window // 60)} MINUTES KEPT")

        self.stat_current.set_value(f"{stats['current']} dBm" if stats["current"] is not None else "\u2014", rssi_color(stats["current"]))
        self.stat_average.set_value(f"{stats['average']:.1f} dBm" if stats["average"] is not None else "\u2014")
        self.stat_min.set_value(f"{stats['minimum']} dBm" if stats["minimum"] is not None else "\u2014", PALETTE["orange"])
        self.stat_max.set_value(f"{stats['maximum']} dBm" if stats["maximum"] is not None else "\u2014", PALETTE["green"])
        stability = stats.get("stability", 0.0)
        stability_color = PALETTE["green"] if stability >= 80 else PALETTE["yellow"] if stability >= 55 else PALETTE["orange"]
        self.stat_stability.set_value(f"{stability:.0f}%" if stats["samples"] >= 3 else "\u2014", stability_color)
        self.stat_samples.set_value(str(stats["samples"]), PALETTE["muted"])

        for key, row in self._rows.items():
            row.set_rssi(self.ctx.signals.stats(key).get("current"))

    # ------------------------------------------------------------------
    def _clear(self) -> None:
        self.ctx.signals.clear()
        self._refresh_chart()
        self.notice.show_message("Signal history cleared. Tracking continues from the next scan.", "info", "")
        self.notice.setVisible(True)

    def _export(self) -> None:
        if not self.ctx.signals.tracked:
            self.notice.show_message("Track at least one network before exporting a signal log.", "warning", "")
            self.notice.setVisible(True)
            return
        directory = Path(self.ctx.settings.get("export_dir"))
        try:
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / f"signal-log-{time.strftime('%Y%m%d-%H%M%S')}.csv"
            path = self.ctx.signals.export_csv(str(target))
        except Exception as exc:  # noqa: BLE001 - surface IO problems in the UI
            self.notice.show_message(f"Signal log export failed: {exc}", "error", "Open Settings")
            try:
                self.notice.action_triggered.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.notice.action_triggered.connect(lambda: bus.navigate.emit("settings"))
        else:
            self.notice.show_message(f"Signal log exported to {path}", "good", "Open History")
            try:
                self.notice.action_triggered.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.notice.action_triggered.connect(lambda: bus.navigate.emit("history"))
        self.notice.setVisible(True)

    # ------------------------------------------------------------------
    def on_scan_error(self, message: str) -> None:
        self.notice.show_message(message, "error", "Open Hardware")
        try:
            self.notice.action_triggered.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.notice.action_triggered.connect(lambda: bus.navigate.emit("hardware"))
        self.notice.setVisible(True)
