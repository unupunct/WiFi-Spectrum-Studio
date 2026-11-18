"""Live Spectrum — the signature workspace page."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...core import channels
from ...core.constants import PALETTE, rssi_color
from ...core.events import bus
from ...core.models import Band, ScanSnapshot
from ...services.waterfall_service import PALETTES
from ...workers.tasks import Task
from .. import icons
from ..widgets.base import (
    Badge,
    EmptyState,
    IconButton,
    MetricCard,
    Panel,
    SegmentedControl,
    label,
)
from ..widgets.channel_distribution import ChannelDistributionChart
from ..widgets.insights import InsightsPanel
from ..widgets.network_table import NetworkTable
from ..widgets.notice import NoticeBar
from ..widgets.spectrum_plot import SpectrumPlot
from ..widgets.waterfall import WaterfallView


class LiveSpectrumPage(QWidget):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._band = Band.parse(ctx.settings.get("band"))
        self._snapshot: ScanSnapshot | None = None
        self._mode = "wifi"
        self._fft_busy = False
        self._shown = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(9)

        # -- page header ---------------------------------------------------
        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 2, 0)
        header.setSpacing(10)
        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(0)
        self.title = label("Live Spectrum", 17, PALETTE["text"], 600, 0.2)
        self.subtitle = label(
            "Real-time Wi-Fi channel visualisation, congestion analysis and network discovery",
            9.5,
            PALETTE["muted"],
            400,
            0.1,
        )
        title_col.addWidget(self.title)
        title_col.addWidget(self.subtitle)
        header.addLayout(title_col)
        header.addStretch(1)

        self.scan_button = QPushButton("  Scan Now")
        self.scan_button.setObjectName("Ghost")
        self.scan_button.setIcon(icons.icon("refresh", PALETTE["text_secondary"], 14))
        self.scan_button.setFixedHeight(28)
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.clicked.connect(lambda: self.ctx.monitor.trigger_now())
        header.addWidget(self.scan_button)

        self.pause_button = QPushButton("  Pause")
        self.pause_button.setObjectName("Ghost")
        self.pause_button.setIcon(icons.icon("pause", PALETTE["text_secondary"], 13))
        self.pause_button.setFixedHeight(28)
        self.pause_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_button.clicked.connect(self._toggle_monitor)
        header.addWidget(self.pause_button)
        root.addLayout(header)

        self.notice = NoticeBar()
        root.addWidget(self.notice)

        # -- metric cards --------------------------------------------------
        cards = QHBoxLayout()
        cards.setSpacing(9)
        self.card_aps = MetricCard("Access Points", "discovery", PALETTE["cyan"])
        self.card_band = MetricCard("Active Band", "frequency", PALETTE["green"])
        self.card_signal = MetricCard("Strongest Signal", "signal", PALETTE["green"])
        self.card_channels = MetricCard("Channels in Use", "layers", PALETTE["blue"])
        self.card_congestion = MetricCard("Channel Congestion", "analyzer", PALETTE["orange"])
        for card in (self.card_aps, self.card_band, self.card_signal, self.card_channels, self.card_congestion):
            cards.addWidget(card, 1)
        root.addLayout(cards)

        # -- band / mode row ----------------------------------------------
        row = QHBoxLayout()
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(10)
        self.band_tabs = SegmentedControl(
            [(Band.GHZ_24.key, "2.4 GHz"), (Band.GHZ_5.key, "5 GHz"), (Band.GHZ_6.key, "6 GHz")]
        )
        self.band_tabs.set_current(self._band.key)
        self.band_tabs.changed.connect(self._on_band_selected)
        row.addWidget(self.band_tabs)

        self.mode_tabs = SegmentedControl([("wifi", "Wi-Fi"), ("fft", "FFT")])
        self.mode_tabs.set_current("wifi")
        self.mode_tabs.changed.connect(self._on_mode_selected)
        row.addWidget(self.mode_tabs)

        self.data_hint = label("", 8.5, PALETTE["muted"], 400, 0.3)
        row.addStretch(1)
        self.scan_hint = label("", 8.5, PALETTE["muted"], 400, 0.3)
        row.addSpacing(14)
        row.addWidget(self.scan_hint)
        row.addSpacing(14)
        row.addWidget(self.data_hint)
        root.addLayout(row)

        # -- spectrum ------------------------------------------------------
        self.spectrum_panel = Panel(
            "Spectrum Analysis",
            "CHANNEL-SHAPED VIEW OF OBSERVED NETWORKS",
        )
        self.network_badge = Badge("0 NETWORKS")
        self.spectrum_panel.add_action(self.network_badge)
        self.auto_button = IconButton("eye", "Toggle automatic Y scaling", 24, 13)
        self.auto_button.setCheckable(True)
        self.auto_button.setChecked(True)
        self.auto_button.toggled.connect(self._on_auto_scale)
        self.spectrum_panel.add_action(self.auto_button)
        self.reset_button = IconButton("maximize", "Reset zoom (double-click the graph)", 24, 13)
        self.reset_button.clicked.connect(self._reset_zoom)
        self.spectrum_panel.add_action(self.reset_button)

        self.spectrum_stack = QStackedWidget()
        self.spectrum = SpectrumPlot(self._band)
        self.spectrum.network_selected.connect(bus.inspect_network.emit)
        self.spectrum_empty = EmptyState(
            "spectrum",
            "No access points observed in this band",
            "Scanning continues in the background. Check the adapter band support or select "
            "another band. No values are fabricated when real data is unavailable.",
        )
        self.spectrum_stack.addWidget(self.spectrum)
        self.spectrum_stack.addWidget(self.spectrum_empty)
        self.spectrum_panel.add(self.spectrum_stack, 1)
        root.addWidget(self.spectrum_panel, 1)

        # -- waterfall -----------------------------------------------------
        self.waterfall_panel = Panel("Waterfall View", "WI-FI OBSERVATION TIMELINE")
        self.waterfall = WaterfallView()
        self.waterfall.state_changed.connect(self._on_waterfall_state)

        self.wf_play = IconButton("play", "Start", 24, 12, PALETTE["green"])
        self.wf_play.clicked.connect(self._wf_start)
        self.wf_pause = IconButton("pause", "Pause", 24, 12)
        self.wf_pause.clicked.connect(self._wf_pause)
        self.wf_stop = IconButton("stop", "Stop", 24, 12)
        self.wf_stop.clicked.connect(lambda: self.waterfall.stop())
        self.wf_clear = IconButton("trash", "Clear history", 24, 12)
        self.wf_clear.clicked.connect(self.waterfall.clear)
        self.wf_zoom = QPushButton("1\u00d7")
        self.wf_zoom.setObjectName("Ghost")
        self.wf_zoom.setFixedSize(34, 24)
        self.wf_zoom.setStyleSheet("font-size: 9px; padding: 0px;")
        self.wf_zoom.setToolTip("Zoom waterfall (mouse wheel)")
        self.wf_zoom.clicked.connect(self._wf_cycle_zoom)
        self.wf_palette = QComboBox()
        self.wf_palette.addItems(list(PALETTES.keys()))
        self.wf_palette.setFixedSize(92, 24)
        self.wf_palette.setStyleSheet("font-size: 9px; padding: 1px 6px; min-height: 18px;")
        self.wf_palette.setToolTip("Waterfall colour palette")
        self.wf_palette.currentTextChanged.connect(self._wf_set_palette)

        for widget in (self.wf_play, self.wf_pause, self.wf_stop, self.wf_clear):
            self.waterfall_panel.add_action(widget)
        self.waterfall_panel.add_action(self.wf_zoom)
        self.waterfall_panel.add_action(self.wf_palette)
        self.waterfall_panel.add(self.waterfall, 1)
        self.waterfall_panel.setFixedHeight(132)
        root.addWidget(self.waterfall_panel)

        # -- bottom row ----------------------------------------------------
        bottom = QHBoxLayout()
        bottom.setSpacing(9)

        self.dist_panel = Panel("Channel Distribution", self._band.label.upper())
        self.dist_badge = Badge("0 APs", PALETTE["cyan"])
        self.dist_panel.add_action(self.dist_badge)
        self.chart = ChannelDistributionChart()
        self.dist_panel.add(self.chart, 1)
        bottom.addWidget(self.dist_panel, 145)

        self.net_panel = Panel("Detected Networks", "SORTED BY SIGNAL")
        self.view_all = QPushButton("View All")
        self.view_all.setObjectName("Link")
        self.view_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_all.clicked.connect(lambda: bus.navigate.emit("discovery"))
        self.net_panel.add_action(self.view_all)
        self.net_badge = Badge("0", PALETTE["cyan"])
        self.net_panel.add_action(self.net_badge)

        self.net_stack = QStackedWidget()
        self.table = NetworkTable()
        self.table.network_selected.connect(bus.inspect_network.emit)
        self.table_empty = EmptyState(
            "discovery",
            "No networks detected",
            "Start monitoring to populate real observations.",
            "Scan Now",
        )
        if self.table_empty.button:
            self.table_empty.button.clicked.connect(lambda: self.ctx.monitor.trigger_now())
        self.net_stack.addWidget(self.table)
        self.net_stack.addWidget(self.table_empty)
        self.net_panel.add(self.net_stack, 1)
        bottom.addWidget(self.net_panel, 115)

        self.insights = InsightsPanel()
        self.insights.analyze_requested.connect(lambda: bus.navigate.emit("analyzer"))
        bottom.addWidget(self.insights, 95)

        for panel in (self.dist_panel, self.net_panel, self.insights):
            panel.setFixedHeight(222)
        root.addLayout(bottom)

        # -- wiring --------------------------------------------------------
        ctx.settings.changed.connect(self._on_setting)
        ctx.monitor.state_changed.connect(self._on_monitor_state)
        self._update_band_support()
        self._apply_band(self._band, push=False)
        self.waterfall.set_palette(ctx.settings.get("waterfall_palette", "Spectrum"))
        self.wf_palette.setCurrentText(ctx.settings.get("waterfall_palette", "Spectrum"))
        self.waterfall.start()

        sdr_ok, sdr_reason = ctx.sdr.probe()
        if not sdr_ok:
            self.mode_tabs.set_disabled({"fft"})
            self.mode_tabs.setToolTip("FFT spectrum requires SoapySDR hardware.\n" + sdr_reason)

        self._fft_timer = QTimer(self)
        self._fft_timer.setInterval(600)
        self._fft_timer.timeout.connect(self._capture_fft)

    # ------------------------------------------------------------------
    # page lifecycle
    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self._shown = True
        if self.ctx.monitor.state == "stopped":
            self.ctx.monitor.start()
        self._refresh()

    def on_snapshot(self, snapshot: ScanSnapshot) -> None:
        self._snapshot = snapshot
        self._update_band_support()
        if snapshot.demo:
            self.notice.show_message(
                "Demonstration mode is active \u2014 every observation on this screen is simulated "
                "and is clearly marked. Disable demo mode in Settings to scan real hardware.",
                "info",
                "Open Settings",
            )
            self._connect_notice("settings")
        elif snapshot.total == 0:
            self.notice.show_message(
                "No wireless networks were detected in the last scan. Monitoring continues.",
                "warning",
                "Open Hardware",
            )
            self._connect_notice("hardware")
        else:
            self.notice.setVisible(False)
        self._refresh()

    def on_scan_error(self, message: str) -> None:
        self.notice.show_message(message, "error", "Open Hardware")
        self._connect_notice("hardware")

    def on_scan_started(self) -> None:
        self.scan_hint.setText("scanning\u2026")

    def _notice_connected(self, target: str) -> bool:
        return getattr(self, "_notice_target", None) == target

    def _connect_notice(self, target: str) -> None:
        if getattr(self, "_notice_target", None) == target:
            return
        if getattr(self, "_notice_target", None):
            try:
                self.notice.action_triggered.disconnect()
            except (RuntimeError, TypeError):
                pass
        if target == "settings":
            self.notice.action_triggered.connect(lambda: bus.navigate.emit("settings"))
        else:
            self.notice.action_triggered.connect(lambda: bus.navigate.emit("hardware"))
        self._notice_target = target

    # ------------------------------------------------------------------
    # data rendering
    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        snapshot = self._snapshot
        band = self._band
        aps = snapshot.by_band(band) if snapshot else []
        counts = snapshot.counts_by_channel(band) if snapshot else {}
        congestion = channels.congestion_pct(aps, band)

        self.card_aps.set_value(str(len(aps)), f"{snapshot.total if snapshot else 0} detected overall")
        self.card_band.set_value(band.label, f"{len(channels.band_channels(band))} channels", band.color)
        if aps:
            strongest = max(aps, key=lambda ap: ap.rssi)
            name = strongest.display_ssid if len(strongest.display_ssid) <= 22 else strongest.display_ssid[:21] + "\u2026"
            self.card_signal.set_value(f"{strongest.rssi} dBm", name, rssi_color(strongest.rssi))
        else:
            self.card_signal.set_value("\u2014", "no signal observed", PALETTE["muted"])
        self.card_channels.set_value(
            str(len(counts)),
            f"of {len(channels.band_channels(band))} {band.label} channels",
            PALETTE["blue"],
        )
        if aps:
            if congestion < 25:
                level, color = "low density", PALETTE["green"]
            elif congestion < 50:
                level, color = "moderate density", PALETTE["yellow"]
            elif congestion < 75:
                level, color = "high density", PALETTE["orange"]
            else:
                level, color = "very high density", PALETTE["red"]
            self.card_congestion.set_value(f"{congestion:.0f}%", level, color)
        else:
            self.card_congestion.set_value("\u2014", "no data", PALETTE["muted"])

        self.dist_panel.set_hint(band.label.upper())
        self.dist_badge.setText(f"{len(aps)} AP{'s' if len(aps) != 1 else ''}")

        avg_rssi: dict[int, float] = {}
        for ap in aps:
            avg_rssi.setdefault(ap.channel, [])
            avg_rssi[ap.channel].append(ap.rssi)  # type: ignore[union-attr]
        avg_map = {ch: sum(vals) / len(vals) for ch, vals in avg_rssi.items()}  # type: ignore[arg-type]

        self.chart.set_data(counts, band, avg_map)
        self.table.set_aps(aps, limit=5)
        self.net_stack.setCurrentIndex(0 if aps else 1)
        self.net_badge.setText(str(len(aps)))
        self.net_panel.set_hint("TOP 5 BY SIGNAL" if len(aps) > 5 else "SORTED BY SIGNAL")
        self.network_badge.setText(f"{len(aps)} NETWORKS")

        insights = []
        if snapshot is not None:
            insights = self.ctx.analysis.insights(snapshot, band, snapshot.adapter or self.ctx.adapters.selected)
            self.insights.set_insights(insights)

        if aps:
            self.spectrum_stack.setCurrentIndex(0)
            self.spectrum.set_data(snapshot.aps if snapshot else [], band)
        else:
            self.spectrum.clear()
            self.spectrum_stack.setCurrentIndex(1)

        if snapshot:
            if self._mode == "wifi":
                self._seed_demo_waterfall(snapshot, band)
                self.waterfall.feed(self._demo_jitter(snapshot.aps) if snapshot.demo else snapshot.aps, band)
            self.scan_hint.setText(
                f"scan {snapshot.duration_ms:.0f} ms  \u2022  {snapshot.total} networks"
                if snapshot.duration_ms
                else ""
            )
        self.data_hint.setText(
            "SCAN-DERIVED \u2022 NOT RF POWER" if self._mode == "wifi" else "FFT \u2022 SDR MEASUREMENT"
        )
        self.band_tabs.set_current(band.key)

    # ------------------------------------------------------------------
    # band / mode
    # ------------------------------------------------------------------
    def _update_band_support(self) -> None:
        adapter = self.ctx.adapters.selected
        disabled: set[str] = set()
        if adapter is not None:
            observed = {ap.band for ap in (self._snapshot.aps if self._snapshot else [])}
            for band in Band.all():
                if not adapter.supports(band) and band not in observed:
                    disabled.add(band.key)
        self.band_tabs.set_disabled(disabled)
        if self._band.key in disabled and disabled != {b.key for b in Band.all()}:
            for band in Band.all():
                if band.key not in disabled:
                    self._apply_band(band)
                    break

    def _apply_band(self, band: Band, push: bool = True) -> None:
        self._band = band
        if push:
            self.ctx.settings.set("band", band.key)
        self.spectrum.set_band(band)
        self.waterfall.set_band(band)
        self.chart.set_band(band)
        self.dist_panel.set_hint(band.label.upper())
        self.band_tabs.set_current(band.key)
        self._refresh()

    def _on_band_selected(self, key: str) -> None:
        band = Band.parse(key)
        if band is self._band:
            return
        self._apply_band(band)

    def _on_setting(self, key: str, value) -> None:
        if key == "band":
            band = Band.parse(value)
            if band is not self._band:
                self._apply_band(band, push=False)
        elif key == "waterfall_palette":
            self.waterfall.set_palette(str(value))
            self.wf_palette.setCurrentText(str(value))

    def _on_mode_selected(self, mode: str) -> None:
        if mode == self._mode:
            return
        ok, reason = self.ctx.sdr.probe()
        if mode == "fft" and not ok:
            self.mode_tabs.set_current("wifi")
            self.notice.show_message(f"FFT mode unavailable: {reason}", "warning", "Open Hardware")
            self._connect_notice("hardware")
            return
        self._mode = mode
        self.spectrum.set_mode(mode)
        self.waterfall.set_mode(mode)
        self.spectrum_panel.set_hint(
            "CHANNEL-SHAPED VIEW OF OBSERVED NETWORKS" if mode == "wifi" else "FFT POWER SPECTRUM \u2022 SDR"
        )
        self.waterfall_panel.set_hint("WI-FI OBSERVATION TIMELINE" if mode == "wifi" else "FFT WATERFALL \u2022 SDR")
        if mode == "fft":
            self._fft_timer.start()
        else:
            self._fft_timer.stop()
            self.spectrum.clear()
            self._refresh()
        self.data_hint.setText("SCAN-DERIVED \u2022 NOT RF POWER" if mode == "wifi" else "FFT \u2022 SDR MEASUREMENT")

    def _capture_fft(self) -> None:
        if self._fft_busy or not self.ctx.sdr.available:
            return
        self._fft_busy = True
        lo, hi = channels.band_bounds(self._band)
        center = (lo + hi) / 2.0
        task = Task(self.ctx.sdr.capture_fft, center, 20e6, 1024, None, self._band)
        task.signals.done.connect(self._fft_ready)
        task.signals.failed.connect(self._fft_failed)
        task.signals.finished.connect(lambda: setattr(self, "_fft_busy", False))
        self._tasks = getattr(self, "_tasks", [])
        self._tasks.append(task)
        QThreadPool.globalInstance().start(task)

    def _fft_ready(self, frame) -> None:
        if frame is None:
            self._fft_failed("No samples were returned by the SDR device.")
            return
        self.spectrum.set_fft_frame(frame.frequencies, frame.power_db, self._band)
        self.waterfall.feed_fft(frame, self._band)

    def _fft_failed(self, message: str) -> None:
        self._fft_timer.stop()
        self.notice.show_message(f"SDR capture failed: {message}", "error", "Open Hardware")
        self._connect_notice("hardware")

    # ------------------------------------------------------------------
    # controls
    # ------------------------------------------------------------------
    def _toggle_monitor(self) -> None:
        monitor = self.ctx.monitor
        if monitor.state == "running":
            monitor.pause()
        else:
            monitor.resume()

    def _on_monitor_state(self, state: str) -> None:
        running = state == "running"
        self.pause_button.setText("  Pause" if running else "  Resume")
        self.pause_button.setIcon(icons.icon("pause" if running else "play", PALETTE["text_secondary"], 13))

    def _on_auto_scale(self, enabled: bool) -> None:
        self.spectrum.set_auto_y(enabled)
        if enabled and self._snapshot:
            self.spectrum.set_data(self._snapshot.aps, self._band)

    def _reset_zoom(self) -> None:
        lo, hi = channels.band_bounds(self._band)
        self.spectrum.plot.setXRange(lo, hi, padding=0.01)
        if self._snapshot:
            self.spectrum.set_data(self._snapshot.aps, self._band)

    def _wf_start(self) -> None:
        self.waterfall.start()
        self.waterfall.clear()

    def _wf_pause(self) -> None:
        if self.waterfall.state == "paused":
            self.waterfall.resume()
        else:
            self.waterfall.pause()

    def _on_waterfall_state(self, state: str) -> None:
        self.wf_play.set_icon_name("play", PALETTE["green"])
        self.wf_pause.set_icon_name("pause", PALETTE["yellow"] if state == "paused" else PALETTE["text_secondary"])
        self.wf_play.setToolTip("Start" if state != "running" else "Restart")
        self.wf_pause.setToolTip("Resume" if state == "paused" else "Pause")

    def _wf_cycle_zoom(self) -> None:
        factor = self.waterfall.zoom * 2
        if factor > 8:
            factor = 1
        self.waterfall.set_zoom(factor)
        self.wf_zoom.setText(f"{factor}\u00d7")

    def _wf_set_palette(self, name: str) -> None:
        self.waterfall.set_palette(name)
        self.ctx.settings.set("waterfall_palette", name)

    def _demo_jitter(self, aps):
        """Add a tiny wobble to simulated rows so the demo waterfall breathes.

        Only ever applied to demonstration data; real hardware rows are fed
        exactly as scanned.
        """
        import random
        from dataclasses import replace

        rng = random.Random()
        return [
            replace(ap, rssi=max(-95, min(-25, ap.rssi + rng.choice((-2, -1, 0, 0, 1, 2)))))
            for ap in aps
        ]

    def _seed_demo_waterfall(self, snapshot: ScanSnapshot, band: Band) -> None:
        """Fill the waterfall with a labelled demo history.

        Only used in demonstration mode, where every value is simulated and
        marked as such. Real hardware always starts from an empty buffer.
        """
        if not snapshot.demo:
            return
        service = self.waterfall.service
        if not service.is_empty():
            return
        aps = [ap for ap in snapshot.aps if ap.band is band]
        if not aps:
            return
        import math
        import random
        from dataclasses import replace

        rng = random.Random(7)
        drift = [0.0] * len(aps)
        total = max(1, service.rows)
        for index in range(total):
            t = index / (total - 1) if total > 1 else 0.0
            faded = []
            for position, ap in enumerate(aps):
                drift[position] = max(-3.2, min(3.2, drift[position] + rng.uniform(-0.75, 0.75)))
                # slow, per-network breathing so the timeline never looks stamped
                breathe = 2.6 * math.sin((t * 2.2 + position * 0.37) * math.tau)
                faded.append(replace(ap, rssi=int(round(ap.rssi + drift[position] + breathe))))
            service.push_row(service.row_from_aps(faded, band))
        self.waterfall.update()
