"""Frequency Explorer: every observed channel mapped across all three bands."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import PALETTE, rssi_color
from ...core.events import bus
from ...core.models import Band, ScanSnapshot
from .. import icons
from ..widgets.base import (
    Badge,
    MeterBar,
    PageHeader,
    Panel,
    SegmentedControl,
    label,
)
from ..widgets.channel_map import ChannelMap
from ..widgets.data_table import DataTable


class FrequencyExplorerPage(QWidget):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._snapshot: ScanSnapshot | None = None
        self._filter = "all"
        self._rows: list = []

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(9)

        header = PageHeader(
            "Frequency Explorer",
            "See how observed networks spread across 2.4, 5 and 6 GHz",
        )
        self.analyzer_button = QPushButton("  Open Channel Analyzer")
        self.analyzer_button.setObjectName("Primary")
        self.analyzer_button.setIcon(icons.icon("analyzer", "#04121F", 14))
        self.analyzer_button.setFixedHeight(28)
        self.analyzer_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analyzer_button.clicked.connect(lambda: bus.navigate.emit("analyzer"))
        header.add_action(self.analyzer_button)
        root.addWidget(header)

        top = QHBoxLayout()
        top.setSpacing(9)

        self.map_panel = Panel("Channel Map", "OCCUPANCY ACROSS EVERY SUPPORTED CHANNEL")
        self.map_badge = Badge("0 NETWORKS", PALETTE["cyan"])
        self.map_panel.add_action(self.map_badge)
        self.channel_map = ChannelMap()
        self.channel_map.band_clicked.connect(self._open_band)
        self.map_panel.add(self.channel_map, 1)

        legend = QHBoxLayout()
        legend.setSpacing(10)
        legend.addWidget(label("OBSERVED NETWORKS", 7.2, PALETTE["muted"], 600, 0.7))
        swatch_colors = [
            ("none", "#0B2130"),
            ("1", "rgba(0, 217, 245, 0.28)"),
            ("2", "rgba(0, 217, 245, 0.52)"),
            ("3+", "rgba(255, 194, 71, 0.45)"),
        ]
        for text, color in swatch_colors:
            swatch = QWidget()
            swatch.setFixedSize(9, 9)
            swatch.setStyleSheet(f"background: {color}; border: 1px solid rgba(23,70,91,0.6); border-radius: 2px;")
            legend.addWidget(swatch)
            legend.addWidget(label(text, 7.2, PALETTE["muted"], 500, 0.3))
        legend.addStretch(1)
        self.map_panel.add_layout(legend)
        top.addWidget(self.map_panel, 1)

        self.summary_panel = Panel("Band Summary", "CURRENT SCAN")
        self.summary: dict[Band, tuple] = {}
        for band in Band.all():
            block = QWidget()
            box = QVBoxLayout(block)
            box.setContentsMargins(0, 2, 0, 2)
            box.setSpacing(2)
            head = QHBoxLayout()
            head.setSpacing(6)
            dot = QWidget()
            dot.setFixedSize(7, 7)
            dot.setStyleSheet(f"background: {band.color}; border-radius: 3px;")
            head.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
            head.addWidget(label(band.label, 10, PALETTE["text"], 600, 0.2), 1)
            count_label = label("0 APs", 9, PALETTE["muted"], 500, 0.2)
            head.addWidget(count_label)
            box.addLayout(head)
            meter = MeterBar(0, band.color, 5)
            box.addWidget(meter)
            detail = label("no observations", 7.8, PALETTE["muted"], 400, 0.2)
            box.addWidget(detail)
            self.summary[band] = (count_label, meter, detail)
            self.summary_panel.add(block)
        self.summary_panel.body.addStretch(1)
        note = label(
            "Cells mark observed channels on their centre frequency. 2.4 GHz channels are "
            "5 MHz apart and drawn as narrow slots to stay legible.",
            7.8,
            PALETTE["muted"],
            400,
            0.05,
            wrap=True,
        )
        self.summary_panel.add(note)
        self.summary_panel.setFixedWidth(320)
        top.addWidget(self.summary_panel)
        root.addLayout(top, 5)

        # -- frequencies table --------------------------------------------
        self.table_panel = Panel("Observed Frequencies", "SORTED BY CENTRE FREQUENCY")
        self.table_badge = Badge("0", PALETTE["cyan"])
        self.table_panel.add_action(self.table_badge)
        self.band_filter = SegmentedControl(
            [
                ("all", "All"),
                (Band.GHZ_24.key, "2.4 GHz"),
                (Band.GHZ_5.key, "5 GHz"),
                (Band.GHZ_6.key, "6 GHz"),
            ]
        )
        self.band_filter.set_current("all")
        self.band_filter.changed.connect(self._on_filter)
        self.table_panel.add_action(self.band_filter)
        self.table = DataTable(
            ["SSID", "BSSID", "BAND", "CH", "FREQ", "WIDTH", "RSSI", "SECURITY"],
            row_height=26,
            stretch_column=0,
            mono_columns=(1, 3, 4, 5),
            widths={1: 118, 2: 46, 3: 40, 4: 54, 5: 62},
        )
        self.table.cellClicked.connect(self._inspect_row)
        self.table_panel.add(self.table, 1)
        self.table_hint = label(
            "Click a row to inspect the full observation \u2022 values are scan-derived",
            8,
            PALETTE["muted"],
            400,
            0.3,
        )
        self.table_panel.add(self.table_hint)
        root.addWidget(self.table_panel, 4)
        ctx.monitor.snapshot_ready.connect(self.on_snapshot)
        self._refresh()

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self._refresh()

    def on_snapshot(self, snapshot: ScanSnapshot) -> None:
        self._snapshot = snapshot
        self._refresh()

    def _on_filter(self, key: str) -> None:
        self._filter = key
        self._refresh_table()

    def _open_band(self, key: str) -> None:
        self.ctx.settings.set("band", key)
        bus.navigate.emit("analyzer")

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        snapshot = self._snapshot
        aps = snapshot.aps if snapshot else []
        self.channel_map.set_snapshot(snapshot)
        self.map_badge.setText(f"{len(aps)} NETWORKS")

        total = max(1, len(aps))
        for band in Band.all():
            band_aps = [ap for ap in aps if ap.band is band]
            counts = {ap.channel for ap in band_aps}
            count_label, meter, detail = self.summary[band]
            count_label.setText(f"{len(band_aps)} AP{'s' if len(band_aps) != 1 else ''}")
            meter.set_value(100.0 * len(band_aps) / total if aps else 0, band.color)
            if band_aps:
                widest = max(ap.width_mhz for ap in band_aps)
                average = sum(ap.rssi for ap in band_aps) / len(band_aps)
                detail.setText(f"{len(counts)} channels \u2022 up to {widest} MHz \u2022 avg {average:.0f} dBm")
            else:
                detail.setText("no observations")
            detail.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")

        self._refresh_table()

    def _refresh_table(self) -> None:
        snapshot = self._snapshot
        aps = list(snapshot.aps) if snapshot else []
        if self._filter != "all":
            band = Band.parse(self._filter)
            aps = [ap for ap in aps if ap.band is band]
        aps.sort(key=lambda ap: (ap.frequency_mhz, ap.ssid.lower()))
        self._rows = aps
        self.table.setRowCount(0)
        for ap in aps:
            self.table.append_row(
                [
                    ap.display_ssid,
                    ap.bssid.upper(),
                    ap.band.short,
                    str(ap.channel),
                    str(ap.frequency_mhz),
                    f"{ap.width_mhz} MHz",
                    f"{ap.rssi} dBm",
                    ap.security,
                ],
                colors={2: ap.band.color, 6: rssi_color(ap.rssi)},
                align={3: Qt.AlignmentFlag.AlignCenter, 4: Qt.AlignmentFlag.AlignRight},
            )
        if not aps:
            self.table.empty_note(
                "No observations yet \u2014 start monitoring to populate the frequency map"
                if snapshot is None or snapshot.total == 0
                else "No networks observed in this band"
            )
        self.table_badge.setText(str(len(aps)))

    def _inspect_row(self, row: int, _column: int) -> None:
        if 0 <= row < len(self._rows):
            bus.inspect_network.emit(self._rows[row].bssid)
