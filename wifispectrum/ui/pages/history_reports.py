"""History & Reports: stored scans, scan detail and report exports."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import PALETTE
from ...core.events import bus
from ...core.models import AccessPoint, Band, ScanSnapshot
from .. import icons
from ..widgets.base import (
    Badge,
    EmptyState,
    KeyValueRow,
    MetricCard,
    PageHeader,
    Panel,
    label,
)
from ..widgets.data_table import DataTable
from ..widgets.network_table import NetworkTable
from ..widgets.notice import NoticeBar


class HistoryReportsPage(QWidget):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._snapshot: ScanSnapshot | None = None
        self._scans: list[dict] = []
        self._selected: dict | None = None
        self._last_refresh = 0.0

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(9)

        header = PageHeader(
            "History & Reports",
            "Review stored scans and export the current environment as a report",
        )
        self.format = QComboBox()
        self.format.addItem("HTML report", "html")
        self.format.addItem("CSV networks", "csv")
        self.format.addItem("JSON data", "json")
        self.format.addItem("PDF report", "pdf")
        self.format.setFixedWidth(132)
        header.add_action(self.format)

        self.export_button = QPushButton("  Export")
        self.export_button.setObjectName("Primary")
        self.export_button.setIcon(icons.icon("download", "#04121F", 14))
        self.export_button.setFixedHeight(28)
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_button.clicked.connect(self._export)
        header.add_action(self.export_button)

        self.clear_button = QPushButton("  Clear History")
        self.clear_button.setObjectName("Danger")
        self.clear_button.setFixedHeight(28)
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(self._clear)
        header.add_action(self.clear_button)
        root.addWidget(header)

        self.notice = NoticeBar()
        root.addWidget(self.notice)

        cards = QHBoxLayout()
        cards.setSpacing(9)
        self.card_scans = MetricCard("Scans Recorded", "history", PALETTE["cyan"])
        self.card_observations = MetricCard("Stored Observations", "layers", PALETTE["blue"])
        self.card_size = MetricCard("Database Size", "doc", PALETTE["green"])
        self.card_retention = MetricCard("Retention", "calendar", PALETTE["yellow"])
        for card in (self.card_scans, self.card_observations, self.card_size, self.card_retention):
            cards.addWidget(card, 1)
        root.addLayout(cards)

        body = QHBoxLayout()
        body.setSpacing(9)

        self.scans_panel = Panel("Recent Scans", "NEWEST FIRST")
        self.scans_badge = Badge("0", PALETTE["cyan"])
        self.scans_panel.add_action(self.scans_badge)
        self.scans_table = DataTable(
            ["TIME", "BAND", "NETWORKS", "DURATION", "SOURCE"],
            row_height=27,
            stretch_column=4,
            mono_columns=(0, 3),
            widths={0: 128, 1: 66, 2: 78, 3: 78},
        )
        self.scans_table.cellClicked.connect(self._select_scan)
        self.scans_panel.add(self.scans_table, 1)
        body.addWidget(self.scans_panel, 52)

        self.detail_panel = Panel("Scan Detail", "SELECT A SCAN")
        self.detail_badge = Badge("NO SELECTION", PALETTE["muted"])
        self.detail_panel.add_action(self.detail_badge)

        self.detail_stack = QStackedWidget()

        self.detail_empty = EmptyState(
            "history",
            "No scan selected",
            "Choose a row in Recent Scans to inspect the networks captured at that moment.",
        )
        self.detail_stack.addWidget(self.detail_empty)

        self.detail_content = QWidget()
        content_layout = QVBoxLayout(self.detail_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        self.detail_head = QWidget()
        head_layout = QHBoxLayout(self.detail_head)
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(18)
        self.detail_rows = {
            "time": KeyValueRow("Timestamp", "\u2014"),
            "networks": KeyValueRow("Networks", "\u2014"),
            "duration": KeyValueRow("Duration", "\u2014"),
            "adapter": KeyValueRow("Adapter", "\u2014"),
        }
        for row in self.detail_rows.values():
            head_layout.addWidget(row, 1)
        content_layout.addWidget(self.detail_head)
        self.recommendation = label(
            "Select a stored scan to see its strongest networks.",
            9,
            PALETTE["muted"],
            400,
            0.1,
        )
        content_layout.addWidget(self.recommendation)

        self.detail_table = NetworkTable(show_band=True)
        self.detail_table.network_selected.connect(bus.inspect_network.emit)
        content_layout.addWidget(self.detail_table, 1)
        self.detail_stack.addWidget(self.detail_content)

        self.detail_panel.add(self.detail_stack, 1)
        body.addWidget(self.detail_panel, 48)
        root.addLayout(body, 1)

        ctx.monitor.snapshot_ready.connect(self.on_snapshot)
        self._refresh()

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self._refresh()

    def on_snapshot(self, snapshot: ScanSnapshot) -> None:
        self._snapshot = snapshot
        self.export_button.setEnabled(snapshot.total > 0)
        if not self.isVisible():
            return
        now = time.time()
        if now - self._last_refresh < 2.5:
            return
        self._last_refresh = now
        self._refresh()

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        history = self.ctx.history
        available = bool(history and history.available)
        self.clear_button.setEnabled(available)
        self.export_button.setEnabled(available and bool(self._snapshot and self._snapshot.aps))
        if not available:
            self.scans_table.clear_rows()
            self.scans_table.empty_note("History database unavailable")
            self.detail_table.set_aps([])
            self.recommendation.setText("History is unavailable, so no scans can be listed.")
            return

        self._scans = history.recent_scans(limit=80)
        self.scans_badge.setText(str(len(self._scans)))
        self.scans_table.clearSpans()
        self.scans_table.setRowCount(0)
        for scan in self._scans:
            stamp = time.strftime("%d %b %H:%M:%S", time.localtime(scan["ts"]))
            band = Band.parse(scan.get("band")).label if scan.get("band") else "\u2014"
            self.scans_table.append_row(
                [
                    stamp,
                    band,
                    str(scan["total"]),
                    f"{scan['duration_ms'] or 0:.0f} ms",
                    "demo" if scan["demo"] else (scan.get("backend") or "scan"),
                ],
                colors={2: PALETTE["text"], 4: PALETTE["yellow"] if scan["demo"] else PALETTE["text_secondary"]},
            )

        scans = history.scan_count()
        observations = history.observation_count()
        size = history.db_size()
        self.card_scans.set_value(str(scans), "stored scan records" if scans else "nothing recorded yet")
        self.card_observations.set_value(str(observations), "network observations", PALETTE["blue"])
        self.card_size.set_value(
            f"{size / 1024:.0f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f} MB",
            "SQLite WAL database",
            PALETTE["green"],
        )
        retention = int(self.ctx.settings.get("retention_days", 30))
        self.card_retention.set_value(f"{retention} days", "older scans are pruned")
        self.clear_button.setEnabled(bool(scans))

        if self._selected:
            current = next((s for s in self._scans if s["id"] == self._selected["id"]), None)
            if current:
                self._show_scan(current)
            else:
                self._selected = None
                self.detail_stack.setCurrentIndex(0)

    # ------------------------------------------------------------------
    def _select_scan(self, row: int, _column: int) -> None:
        if 0 <= row < len(self._scans):
            self._show_scan(self._scans[row])

    def _show_scan(self, scan: dict) -> None:
        self._selected = scan
        self.detail_stack.setCurrentIndex(1)
        history = self.ctx.history
        if history is None:
            return
        self.detail_badge.setText("STORED SCAN")
        self.detail_badge.setStyleSheet(
            f"color: {PALETTE['cyan']}; background: rgba(0, 217, 245, 0.10);"
            " border: 1px solid rgba(0, 217, 245, 0.32); border-radius: 7px; padding: 1px 7px;"
        )
        self.detail_rows["time"].set_value(time.strftime("%d %b %Y %H:%M:%S", time.localtime(scan["ts"])))
        self.detail_rows["networks"].set_value(str(scan["total"]))
        self.detail_rows["duration"].set_value(f"{scan['duration_ms'] or 0:.0f} ms")
        self.detail_rows["adapter"].set_value(scan.get("adapter_name") or scan.get("adapter") or "unknown")
        self.detail_panel.set_hint(time.strftime("SCAN #%H%M%S", time.localtime(scan["ts"])))

        rows = history.scan_networks(scan["id"])
        aps = [
            AccessPoint(
                bssid=row["bssid"],
                ssid=row["ssid"],
                channel=row["channel"] or 0,
                frequency_mhz=row["frequency_mhz"] or 0,
                width_mhz=row["width_mhz"] or 20,
                rssi=row["rssi"] or -100,
                security=row["security"] or "Open",
                vendor=row["vendor"] or "Unknown",
                phy=row["phy"] or "",
            )
            for row in rows
        ]
        self.detail_table.set_aps(aps, limit=12)

        if rows:
            band = Band.parse(scan.get("band"))
            snapshot = ScanSnapshot(aps=aps, timestamp=scan["ts"], demo=bool(scan.get("demo")))
            assessment = self.ctx.analysis.assess(snapshot, band)
            if assessment.recommendation:
                rec = assessment.recommendation
                self.recommendation.setText(
                    f"Recommended channel at capture time: ch {rec.channel} "
                    f"({rec.frequency_mhz} MHz) \u2022 {rec.confidence} confidence \u2022 "
                    f"{len(aps)} networks stored"
                )
                self.recommendation.setStyleSheet(f"color: {PALETTE['cyan']}; background: transparent;")
            else:
                self.recommendation.setText(f"{len(aps)} networks stored for this scan.")
                self.recommendation.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")
        else:
            self.detail_table.set_aps([])
            self.recommendation.setText(
                "This scan stored no per-network observations (observations are sampled to limit database growth)."
            )
            self.recommendation.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")

    # ------------------------------------------------------------------
    def _export(self) -> None:
        snapshot = self._snapshot
        if snapshot is None or not snapshot.aps:
            return
        choice = self.format.currentData()
        band = Band.parse(self.ctx.settings.get("band"))
        try:
            assessment = self.ctx.analysis.assess(snapshot, band)
            insights = self.ctx.analysis.insights(snapshot, band, snapshot.adapter or self.ctx.adapters.selected)
            if choice == "csv":
                path = self.ctx.reports.export_csv(snapshot)
            elif choice == "json":
                path = self.ctx.reports.export_json(snapshot, assessment, insights)
            elif choice == "pdf":
                path = self.ctx.reports.export_pdf(snapshot, assessment, insights)
            else:
                path = self.ctx.reports.export_html(snapshot, assessment, insights)
        except Exception as exc:  # noqa: BLE001 - surface export problems in the UI
            self.notice.show_message(f"Export failed: {exc}", "error", "Open Settings")
            try:
                self.notice.action_triggered.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.notice.action_triggered.connect(lambda: bus.navigate.emit("settings"))
        else:
            self.notice.show_message(f"Report exported to {path}", "good", "")
        self.notice.setVisible(True)

    def _clear(self) -> None:
        history = self.ctx.history
        if history is None:
            return
        answer = QMessageBox.question(
            self,
            "Clear history",
            "Delete every stored scan, observation and recommendation? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        history.clear()
        self._selected = None
        self.detail_badge.setText("NO SELECTION")
        self.detail_table.set_aps([])
        self.detail_stack.setCurrentIndex(0)
        self._refresh()
        self.notice.show_message("History cleared.", "info", "")
        self.notice.setVisible(True)
