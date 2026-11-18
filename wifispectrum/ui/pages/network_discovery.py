"""Network Discovery: searchable, filterable view of every observed BSS."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import PALETTE
from ...core.events import bus
from ...core.models import Band, ScanSnapshot
from .. import icons
from ..widgets.base import (
    Badge,
    EmptyState,
    PageHeader,
    Panel,
    SearchField,
    SegmentedControl,
    label,
)
from ..widgets.network_table import NetworkTable
from ..widgets.notice import NoticeBar


class NetworkDiscoveryPage(QWidget):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._snapshot: ScanSnapshot | None = None
        self._empty_mode = "no_data"

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(9)

        header = PageHeader(
            "Network Discovery",
            "Every access point from the latest scan, searchable and grouped by band",
        )
        self.export_button = QPushButton("  Export CSV")
        self.export_button.setObjectName("Ghost")
        self.export_button.setIcon(icons.icon("download", PALETTE["text_secondary"], 14))
        self.export_button.setFixedHeight(28)
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_button.clicked.connect(self._export)
        header.add_action(self.export_button)

        self.scan_button = QPushButton("  Scan Now")
        self.scan_button.setObjectName("Primary")
        self.scan_button.setIcon(icons.icon("refresh", "#04121F", 14))
        self.scan_button.setFixedHeight(28)
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.clicked.connect(lambda: self.ctx.monitor.trigger_now())
        header.add_action(self.scan_button)
        root.addWidget(header)

        self.notice = NoticeBar()
        root.addWidget(self.notice)

        # -- filters -------------------------------------------------------
        filters = QHBoxLayout()
        filters.setContentsMargins(2, 0, 2, 0)
        filters.setSpacing(9)
        self.search = SearchField("Search SSID, BSSID or vendor\u2026")
        self.search.setFixedWidth(300)
        self.search.textChanged.connect(lambda _: self._refresh())
        filters.addWidget(self.search)

        self.band_tabs = SegmentedControl(
            [
                ("all", "All bands"),
                (Band.GHZ_24.key, "2.4 GHz"),
                (Band.GHZ_5.key, "5 GHz"),
                (Band.GHZ_6.key, "6 GHz"),
            ]
        )
        self.band_tabs.set_current("all")
        self.band_tabs.changed.connect(lambda _: self._refresh())
        filters.addWidget(self.band_tabs)

        filters.addStretch(1)

        self.sort = QComboBox()
        self.sort.addItem("Strongest signal", "signal")
        self.sort.addItem("Channel order", "channel")
        self.sort.addItem("SSID (A\u2013Z)", "ssid")
        self.sort.addItem("Security", "security")
        self.sort.setFixedWidth(150)
        self.sort.currentIndexChanged.connect(lambda _: self._refresh())
        filters.addWidget(label("SORT", 8, PALETTE["muted"], 600, 1.0))
        filters.addWidget(self.sort)

        self.security = QComboBox()
        for name in ("All security", "Open", "WEP", "WPA", "WPA2", "WPA3"):
            self.security.addItem(name, "all" if name == "All security" else name)
        self.security.setFixedWidth(130)
        self.security.currentIndexChanged.connect(lambda _: self._refresh())
        filters.addWidget(self.security)
        root.addLayout(filters)

        # -- table ---------------------------------------------------------
        self.panel = Panel("Observed Networks", "CLICK A ROW FOR FULL DETAILS")
        self.count_badge = Badge("0 NETWORKS", PALETTE["cyan"])
        self.panel.add_action(self.count_badge)
        self.result_label = label("", 8.4, PALETTE["muted"], 400, 0.2)
        self.panel.add_action(self.result_label)

        self.stack = QStackedWidget()
        self.table = NetworkTable(show_band=True, show_meta=True)
        self.table.network_selected.connect(bus.inspect_network.emit)
        self.empty = EmptyState(
            "discovery",
            "No networks detected yet",
            "Start monitoring to collect real observations. Nothing is fabricated when a scan returns no access points.",
            "Scan Now",
        )
        if self.empty.button:
            self.empty.button.clicked.connect(self._empty_action)
        self.stack.addWidget(self.table)
        self.stack.addWidget(self.empty)
        self.panel.add(self.stack, 1)
        root.addWidget(self.panel, 1)

        self.footer = label(
            "Observed values only \u2022 channel width and RSSI come directly from the scan backend",
            8.2,
            PALETTE["muted"],
            400,
            0.3,
        )
        root.addWidget(self.footer)

        ctx.monitor.snapshot_ready.connect(self.on_snapshot)
        self._refresh()

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self._refresh()
        self.search.setFocus()

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def on_snapshot(self, snapshot: ScanSnapshot) -> None:
        self._snapshot = snapshot
        self._refresh()

    # ------------------------------------------------------------------
    def _visible_aps(self):
        snapshot = self._snapshot
        aps = list(snapshot.aps) if snapshot else []
        band_key = self.band_tabs.current
        if band_key != "all":
            band = Band.parse(band_key)
            aps = [ap for ap in aps if ap.band is band]
        security = self.security.currentData()
        if security and security != "all":
            aps = [ap for ap in aps if ap.security == security]
        query = self.search.text().strip().lower()
        if query:
            aps = [
                ap
                for ap in aps
                if query in ap.display_ssid.lower()
                or query in ap.bssid.lower()
                or query in ap.vendor.lower()
                or query in ap.security.lower()
            ]
        return aps

    def _refresh(self) -> None:
        snapshot = self._snapshot
        total = snapshot.total if snapshot else 0
        aps = self._visible_aps()
        sort_by = self.sort.currentData() or "signal"
        self.table.set_aps(aps, sort_by=sort_by)

        if total == 0:
            self._empty_mode = "no_data"
            self.empty.title.setText("No networks detected yet")
            self.empty.detail.setText(
                "Start monitoring to collect real observations. Nothing is fabricated "
                "when a scan returns no access points."
            )
            if self.empty.button:
                self.empty.button.setText("Scan Now")
            self.stack.setCurrentWidget(self.empty)
        elif not aps:
            self._empty_mode = "no_match"
            self.empty.title.setText("No networks match these filters")
            self.empty.detail.setText(
                "Adjust the search text, band or security filter. The latest scan still holds "
                f"{total} network{'s' if total != 1 else ''}."
            )
            if self.empty.button:
                self.empty.button.setText("Reset filters")
            self.stack.setCurrentWidget(self.empty)
        else:
            self.stack.setCurrentWidget(self.table)

        self.count_badge.setText(f"{total} NETWORKS")
        self.result_label.setText(f"showing {len(aps)}" if len(aps) != total else "")
        self.export_button.setEnabled(total > 0)

    def _empty_action(self) -> None:
        if self._empty_mode == "no_match":
            self.search.clear()
            self.band_tabs.set_current("all")
            self.security.setCurrentIndex(0)
            self._refresh()
        else:
            self.ctx.monitor.trigger_now()

    def _export(self) -> None:
        if self._snapshot is None or not self._snapshot.aps:
            return
        try:
            path = self.ctx.reports.export_csv(self._snapshot)
        except Exception as exc:  # noqa: BLE001 - surface export problems in the UI
            self.notice.show_message(f"CSV export failed: {exc}", "error", "Open Settings")
            try:
                self.notice.action_triggered.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.notice.action_triggered.connect(lambda: bus.navigate.emit("settings"))
        else:
            self.notice.show_message(f"Network list exported to {path}", "good", "Open History")
            try:
                self.notice.action_triggered.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.notice.action_triggered.connect(lambda: bus.navigate.emit("history"))
        self.notice.setVisible(True)
