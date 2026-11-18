"""Dashboard: environment overview, monitoring health and recent activity."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ...core import channels
from ...core.constants import PALETTE, rssi_color
from ...core.events import bus
from ...core.models import Band, ScanSnapshot
from ...services.analysis_service import ChannelAnalysisService
from .. import icons
from ..widgets.band_overview import BandOverview
from ..widgets.base import (
    Badge,
    KeyValueRow,
    MetricCard,
    PageHeader,
    Panel,
    label,
)
from ..widgets.signal_histogram import SignalHistogram


class DashboardPage(QWidget):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._snapshot: ScanSnapshot | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(9)

        header = PageHeader(
            "Dashboard",
            "Wireless environment at a glance: observed bands, density and monitoring health",
        )
        self.scan_button = QPushButton("  Scan Now")
        self.scan_button.setObjectName("Ghost")
        self.scan_button.setIcon(icons.icon("refresh", PALETTE["text_secondary"], 14))
        self.scan_button.setFixedHeight(28)
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.clicked.connect(lambda: self.ctx.monitor.trigger_now())
        header.add_action(self.scan_button)

        self.open_button = QPushButton("  Open Live Spectrum")
        self.open_button.setObjectName("Primary")
        self.open_button.setIcon(icons.icon("spectrum", "#04121F", 14))
        self.open_button.setFixedHeight(28)
        self.open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_button.clicked.connect(lambda: bus.navigate.emit("spectrum"))
        header.add_action(self.open_button)
        root.addWidget(header)

        # -- metric cards --------------------------------------------------
        cards = QHBoxLayout()
        cards.setSpacing(9)
        self.card_networks = MetricCard("Networks", "discovery", PALETTE["cyan"])
        self.card_bands = MetricCard("Bands Active", "frequency", PALETTE["green"])
        self.card_signal = MetricCard("Strongest Signal", "signal", PALETTE["green"])
        self.card_density = MetricCard("Channel Density", "analyzer", PALETTE["orange"])
        self.card_scans = MetricCard("Scans Recorded", "history", PALETTE["blue"])
        for card in (
            self.card_networks,
            self.card_bands,
            self.card_signal,
            self.card_density,
            self.card_scans,
        ):
            cards.addWidget(card, 1)
        root.addLayout(cards)

        # -- band overview + health ---------------------------------------
        middle = QHBoxLayout()
        middle.setSpacing(9)

        self.band_panel = Panel("Band Overview", "OBSERVED NETWORKS PER BAND")
        self.band_count = Badge("0 APs", PALETTE["cyan"])
        self.band_panel.add_action(self.band_count)
        self.overview = BandOverview()
        self.band_panel.add(self.overview, 1)
        middle.addWidget(self.band_panel, 62)

        self.health_panel = Panel("Monitoring Health", "RUNTIME STATUS")
        self.health_badge = Badge("STARTING", PALETTE["muted"])
        self.health_panel.add_action(self.health_badge)
        self.health = {
            "source": KeyValueRow("Data source", "\u2014"),
            "adapter": KeyValueRow("Adapter", "\u2014"),
            "interface": KeyValueRow("Interface", "\u2014"),
            "bands": KeyValueRow("Supported bands", "\u2014"),
            "interval": KeyValueRow("Scan interval", "\u2014"),
            "duration": KeyValueRow("Last scan duration", "\u2014"),
            "history": KeyValueRow("History database", "\u2014"),
            "fft": KeyValueRow("FFT / SDR", "\u2014"),
        }
        for row in self.health.values():
            self.health_panel.add(row)
        middle.addWidget(self.health_panel, 38)
        root.addLayout(middle, 1)

        # -- histogram + recent activity ----------------------------------
        bottom = QHBoxLayout()
        bottom.setSpacing(9)

        self.signal_panel = Panel("Signal Distribution", "OBSERVED NETWORKS BY RSSI")
        self.signal_badge = Badge("0 SAMPLES", PALETTE["cyan"])
        self.signal_panel.add_action(self.signal_badge)
        self.histogram = SignalHistogram()
        self.signal_panel.add(self.histogram, 1)
        bottom.addWidget(self.signal_panel, 58)

        self.activity_panel = Panel("Recent Activity", "LAST COMPLETED SCANS")
        self.view_history = QPushButton("View History")
        self.view_history.setObjectName("Link")
        self.view_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_history.clicked.connect(lambda: bus.navigate.emit("history"))
        self.activity_panel.add_action(self.view_history)
        self.activity_box = QWidget()
        self.activity = QVBoxLayout(self.activity_box)
        self.activity.setContentsMargins(0, 0, 0, 0)
        self.activity.setSpacing(0)
        self.activity_panel.add(self.activity_box, 1)
        bottom.addWidget(self.activity_panel, 42)

        for panel in (self.signal_panel, self.activity_panel):
            panel.setFixedHeight(206)
        root.addLayout(bottom)

        ctx.monitor.state_changed.connect(self._on_state)
        ctx.settings.changed.connect(lambda key, value: self._refresh() if key == "band" else None)
        self._refresh()

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self._refresh()

    def on_snapshot(self, snapshot: ScanSnapshot) -> None:
        self._snapshot = snapshot
        self._refresh()

    def _on_state(self, state: str) -> None:
        colors = {
            "running": PALETTE["green"],
            "paused": PALETTE["yellow"],
            "error": PALETTE["red"],
            "stopped": PALETTE["muted"],
        }
        self.health_badge.setText(state.upper())
        self.health_badge.setStyleSheet(
            f"color: {colors.get(state, PALETTE['muted'])};"
            f" background: {colors.get(state, PALETTE['muted'])}22;"
            f" border: 1px solid {colors.get(state, PALETTE['muted'])}66;"
            " border-radius: 7px; padding: 1px 7px;"
        )

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        snapshot = self._snapshot
        band = Band.parse(self.ctx.settings.get("band"))
        aps = snapshot.aps if snapshot else []
        total = len(aps)

        self.card_networks.set_value(str(total), f"{len({ap.band for ap in aps})} bands represented")
        bands_active = sorted({ap.band for ap in aps}, key=lambda b: b.value)
        self.card_bands.set_value(
            str(len(bands_active)),
            " \u2022 ".join(b.label for b in bands_active) if bands_active else "no observations yet",
            PALETTE["green"] if bands_active else PALETTE["muted"],
        )

        strongest = snapshot.strongest if snapshot else None
        if strongest:
            name = strongest.display_ssid
            if len(name) > 24:
                name = name[:23] + "\u2026"
            self.card_signal.set_value(f"{strongest.rssi} dBm", name, rssi_color(strongest.rssi))
        else:
            self.card_signal.set_value("\u2014", "no signal observed", PALETTE["muted"])

        band_aps = snapshot.by_band(band) if snapshot else []
        density = channels.congestion_pct(band_aps, band)
        color = (
            PALETTE["green"]
            if density < 25
            else PALETTE["yellow"]
            if density < 50
            else PALETTE["orange"]
            if density < 75
            else PALETTE["red"]
        )
        self.card_density.set_value(
            f"{density:.0f}%" if band_aps else "\u2014",
            f"{band.label} band density",
            color if band_aps else PALETTE["muted"],
        )

        history = self.ctx.history
        scans = history.scan_count() if history and history.available else 0
        self.card_scans.set_value(str(scans), "stored in the history database" if history else "history unavailable")

        self.overview.set_bands(snapshot)
        self.band_count.setText(f"{total} AP{'s' if total != 1 else ''}")

        adapter = (snapshot.adapter if snapshot else None) or self.ctx.adapters.selected
        self._update_health(snapshot, adapter, scans)

        histogram = ChannelAnalysisService.signal_histogram(aps)
        self.histogram.set_data(histogram, total)
        self.signal_badge.setText(f"{total} SAMPLE{'S' if total != 1 else ''}")

        self._update_activity()

    # ------------------------------------------------------------------
    def _update_health(self, snapshot: ScanSnapshot | None, adapter, scans: int) -> None:
        demo = bool(snapshot.demo) if snapshot else self.ctx.adapters.is_demo
        source = "Demonstration data" if demo else (snapshot.backend if snapshot else "scan")
        self.health["source"].set_value(source, PALETTE["yellow"] if demo else PALETTE["cyan"])

        if adapter:
            self.health["adapter"].set_value(adapter.name[:26])
            self.health["interface"].set_value(adapter.interface)
            self.health["bands"].set_value(adapter.band_labels)
        else:
            self.health["adapter"].set_value("none detected", PALETTE["muted"])
            self.health["interface"].set_value("\u2014")
            self.health["bands"].set_value("\u2014")

        interval = int(self.ctx.settings.get("scan_interval_ms", 2000)) / 1000.0
        self.health["interval"].set_value(f"{interval:.1f} s")
        duration = snapshot.duration_ms if snapshot else 0.0
        self.health["duration"].set_value(f"{duration:.0f} ms" if duration else "\u2014")
        self.health["history"].set_value(
            f"{scans} scans" if self.ctx.history and self.ctx.history.available else "unavailable",
            PALETTE["muted"] if not self.ctx.history else None,
        )
        sdr_ok, _reason = self.ctx.sdr.probe()
        self.health["fft"].set_value("SoapySDR ready" if sdr_ok else "no SDR detected", PALETTE["green"] if sdr_ok else PALETTE["muted"])

    def _update_activity(self) -> None:
        while self.activity.count():
            item = self.activity.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        history = self.ctx.history
        rows = history.recent_scans(limit=4) if history and history.available else []
        if not rows:
            note = label(
                "Completed scans will appear here once history recording starts.",
                9.2,
                PALETTE["muted"],
                400,
                0.1,
                wrap=True,
            )
            self.activity.addWidget(note)
            self.activity.addStretch(1)
            return

        for index, scan in enumerate(rows):
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(8)

            dot = QWidget()
            dot.setFixedSize(6, 6)
            dot.setStyleSheet(
                f"background: {PALETTE['yellow'] if scan.get('demo') else PALETTE['cyan']}; border-radius: 3px;"
            )
            line.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

            stamp = label(time.strftime("%H:%M:%S", time.localtime(scan["ts"])), 8.6, PALETTE["text_secondary"], 500, 0.2)
            stamp.setFixedWidth(62)
            line.addWidget(stamp)

            network_text = label(f"{scan['total']} networks", 9.2, PALETTE["text"], 500, 0.05)
            line.addWidget(network_text)
            line.addStretch(1)

            band = Band.parse(scan.get("band")).label if scan.get("band") else ""
            if band:
                band_label = label(band, 8, PALETTE["muted"], 500, 0.4)
                line.addWidget(band_label)
            duration = scan.get("duration_ms") or 0
            duration_label = label(f"{duration:.0f} ms", 8, PALETTE["muted"], 400, 0.2)
            duration_label.setFixedWidth(48)
            duration_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            line.addWidget(duration_label)

            row.setFixedHeight(31)
            self.activity.addWidget(row)
            if index < len(rows) - 1:
                divider = QWidget()
                divider.setFixedHeight(1)
                divider.setStyleSheet("background: rgba(23, 70, 91, 0.35);")
                self.activity.addWidget(divider)
        self.activity.addStretch(1)
