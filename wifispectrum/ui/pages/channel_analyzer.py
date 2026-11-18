"""Channel Analyzer: channel scoring, recommendations and full insights."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core import channels
from ...core.constants import PALETTE
from ...core.events import bus
from ...core.models import Band, Insight, ScanSnapshot
from .. import icons
from ..widgets.base import (
    Badge,
    MeterBar,
    PageHeader,
    Panel,
    SegmentedControl,
    StatBlock,
    label,
    rgba,
)
from ..widgets.data_table import DataTable
from ..widgets.interference_chart import InterferenceChart
from ..widgets.notice import NoticeBar


class InsightDetailRow(QWidget):
    def __init__(self, insight: Insight, color: str, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        head = QHBoxLayout()
        head.setSpacing(6)
        dot = QWidget()
        dot.setFixedSize(7, 7)
        dot.setStyleSheet(f"background: {color}; border-radius: 3px;")
        head.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addWidget(label(insight.title, 9.6, PALETTE["text"], 600, 0.05), 1)
        layout.addLayout(head)

        detail = label(insight.detail, 8.4, PALETTE["muted"], 400, 0.05, wrap=True)
        detail.setContentsMargins(13, 0, 0, 0)
        layout.addWidget(detail)

        if insight.measurement:
            meta = label(insight.measurement, 8.2, color, 500, 0.05)
            meta.setContentsMargins(13, 0, 0, 0)
            layout.addWidget(meta)


class ChannelAnalyzerPage(QWidget):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._band = Band.parse(ctx.settings.get("band"))
        self._snapshot: ScanSnapshot | None = None
        self._assessment = None
        self._insights: list[Insight] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(9)

        header = PageHeader(
            "Channel Analyzer",
            "Score every channel from observed networks and find the quietest option",
        )
        self.export_button = QPushButton("  Export Report")
        self.export_button.setObjectName("Ghost")
        self.export_button.setIcon(icons.icon("download", PALETTE["text_secondary"], 14))
        self.export_button.setFixedHeight(28)
        self.export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_button.clicked.connect(self._export)
        header.add_action(self.export_button)
        root.addWidget(header)

        self.notice = NoticeBar()
        self.notice.setVisible(False)
        root.addWidget(self.notice)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(2, 0, 2, 0)
        toolbar.setSpacing(10)
        self.band_tabs = SegmentedControl(
            [(Band.GHZ_24.key, "2.4 GHz"), (Band.GHZ_5.key, "5 GHz"), (Band.GHZ_6.key, "6 GHz")]
        )
        self.band_tabs.set_current(self._band.key)
        self.band_tabs.changed.connect(self._on_band_selected)
        toolbar.addWidget(self.band_tabs)
        toolbar.addStretch(1)
        self.basis = label("OBSERVED CHANNEL OVERLAP \u2022 NOT AIRTIME UTILISATION", 8.2, PALETTE["muted"], 500, 0.8)
        toolbar.addWidget(self.basis)
        self.scan_hint = label("", 8.2, PALETTE["muted"], 400, 0.3)
        toolbar.addSpacing(12)
        toolbar.addWidget(self.scan_hint)
        root.addLayout(toolbar)

        # -- top row -------------------------------------------------------
        top = QHBoxLayout()
        top.setSpacing(9)

        self.rec_panel = Panel("Recommended Channel", "LOWEST OVERLAP")
        self.rec_badge = Badge("NO DATA", PALETTE["muted"])
        self.rec_panel.add_action(self.rec_badge)
        rec_body = QWidget()
        rec_layout = QHBoxLayout(rec_body)
        rec_layout.setContentsMargins(0, 0, 0, 0)
        rec_layout.setSpacing(14)

        channel_col = QVBoxLayout()
        channel_col.setContentsMargins(0, 0, 0, 0)
        channel_col.setSpacing(0)
        channel_line = QHBoxLayout()
        channel_line.setSpacing(4)
        self.rec_channel = label("\u2014", 30, PALETTE["cyan"], 600, 0.2)
        self.rec_channel.setFixedHeight(36)
        channel_line.addWidget(self.rec_channel)
        self.rec_channel_unit = label("CH", 8.5, PALETTE["muted"], 600, 0.8)
        channel_line.addWidget(self.rec_channel_unit, 0, Qt.AlignmentFlag.AlignBottom)
        channel_col.addLayout(channel_line)
        self.rec_freq = label("no channel scored yet", 8.5, PALETTE["muted"], 400, 0.2)
        channel_col.addWidget(self.rec_freq)
        rec_layout.addLayout(channel_col)

        confidence_col = QVBoxLayout()
        confidence_col.setContentsMargins(0, 0, 0, 0)
        confidence_col.setSpacing(4)
        confidence_col.addSpacing(2)
        self.rec_confidence = label("CONFIDENCE \u2014", 8, PALETTE["muted"], 600, 0.7)
        confidence_col.addWidget(self.rec_confidence)
        self.rec_meter = MeterBar(0, PALETTE["cyan"], 6)
        confidence_col.addWidget(self.rec_meter)
        self.rec_reason = label(
            "Complete a scan to score every channel in this band.",
            8.6,
            PALETTE["text_secondary"],
            400,
            0.05,
            wrap=True,
        )
        confidence_col.addWidget(self.rec_reason)
        self.rec_alt = label("", 8.2, PALETTE["muted"], 500, 0.2)
        confidence_col.addWidget(self.rec_alt)
        rec_layout.addLayout(confidence_col, 1)
        self.rec_panel.add(rec_body, 1)
        top.addWidget(self.rec_panel, 40)

        self.density_panel = Panel("Band Congestion", "NETWORK DENSITY ESTIMATE")
        self.density_badge = Badge("0%", PALETTE["green"])
        self.density_panel.add_action(self.density_badge)
        density_body = QWidget()
        density_layout = QVBoxLayout(density_body)
        density_layout.setContentsMargins(0, 0, 0, 0)
        density_layout.setSpacing(5)
        density_layout.addSpacing(2)
        self.density_meter = MeterBar(0, PALETTE["green"], 8)
        density_layout.addWidget(self.density_meter)
        density_layout.addWidget(
            label(
                "Share of the band claimed by observed networks. Not a measured airtime figure.",
                8.2,
                PALETTE["muted"],
                400,
                0.05,
                wrap=True,
            )
        )
        stats = QHBoxLayout()
        stats.setSpacing(16)
        self.busiest = StatBlock("Busiest channel", "\u2014", PALETTE["orange"])
        self.quietest = StatBlock("Quietest channel", "\u2014", PALETTE["green"])
        self.pairs = StatBlock("Overlapping pairs", "\u2014", PALETTE["yellow"])
        stats.addWidget(self.busiest)
        stats.addWidget(self.quietest)
        stats.addWidget(self.pairs)
        stats.addStretch(1)
        density_layout.addLayout(stats)
        density_layout.addStretch(1)
        self.density_panel.add(density_body, 1)
        top.addWidget(self.density_panel, 28)

        self.interference_panel = Panel("Interference Profile", "RELATIVE OVERLAP \u2022 1.00 = BUSIEST")
        self.interference = InterferenceChart()
        self.interference_panel.add(self.interference, 1)
        top.addWidget(self.interference_panel, 32)

        for panel in (self.rec_panel, self.density_panel, self.interference_panel):
            panel.setFixedHeight(178)
        root.addLayout(top)

        # -- bottom row ----------------------------------------------------
        bottom = QHBoxLayout()
        bottom.setSpacing(9)

        self.table_panel = Panel("Channel Assessment", "OBSERVED NETWORKS PER CHANNEL")
        self.table_badge = Badge("0 CHANNELS", PALETTE["cyan"])
        self.table_panel.add_action(self.table_badge)
        self.table = DataTable(
            ["CH", "FREQUENCY", "NETWORKS", "INDEX", "ASSESSMENT"],
            stretch_column=4,
            row_height=27,
            mono_columns=(0, 1, 3),
        )
        self.table_panel.add(self.table, 1)
        bottom.addWidget(self.table_panel, 58)

        self.insights_panel = Panel("Analysis Insights", "GENERATED FROM THIS SCAN")
        self.insights_badge = Badge("0", PALETTE["cyan"])
        self.insights_panel.add_action(self.insights_badge)
        self.insight_scroll = QScrollArea()
        self.insight_scroll.setWidgetResizable(True)
        self.insight_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.insight_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.insight_scroll.setStyleSheet("background: transparent;")
        self.insight_container = QWidget()
        self.insight_container.setStyleSheet("background: transparent;")
        self.insight_rows = QVBoxLayout(self.insight_container)
        self.insight_rows.setContentsMargins(0, 2, 4, 2)
        self.insight_rows.setSpacing(9)
        self.insight_rows.addStretch(1)
        self.insight_scroll.setWidget(self.insight_container)
        self.insights_panel.add(self.insight_scroll, 1)
        bottom.addWidget(self.insights_panel, 42)
        root.addLayout(bottom, 1)

        # -- wiring --------------------------------------------------------
        ctx.monitor.snapshot_ready.connect(self.on_snapshot)
        ctx.settings.changed.connect(self._on_setting)
        self._update_band_support()
        self._refresh()

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self._refresh()

    def on_snapshot(self, snapshot: ScanSnapshot) -> None:
        self._snapshot = snapshot
        self._update_band_support()
        self._refresh()

    # ------------------------------------------------------------------
    def _on_band_selected(self, key: str) -> None:
        band = Band.parse(key)
        if band is self._band:
            return
        self._band = band
        self.ctx.settings.set("band", band.key)
        self._refresh()

    def _on_setting(self, key: str, value) -> None:
        if key == "band" and Band.parse(value) is not self._band:
            self._band = Band.parse(value)
            self.band_tabs.set_current(self._band.key)
            self._refresh()

    def _update_band_support(self) -> None:
        adapter = self.ctx.adapters.selected
        disabled: set[str] = set()
        if adapter is not None:
            observed = {ap.band for ap in (self._snapshot.aps if self._snapshot else [])}
            for band in Band.all():
                if not adapter.supports(band) and band not in observed:
                    disabled.add(band.key)
        self.band_tabs.set_disabled(disabled)

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        snapshot = self._snapshot
        band = self._band
        if snapshot is None:
            self._render_empty(band)
            return

        assessment = self.ctx.analysis.assess(snapshot, band)
        insights = self.ctx.analysis.insights(snapshot, band, snapshot.adapter or self.ctx.adapters.selected)
        self._assessment = assessment
        self._insights = insights
        self.band_tabs.set_current(band.key)
        self.scan_hint.setText(
            "scan {:.0f} ms \u2022 {:,} networks".format(snapshot.duration_ms, snapshot.total)
            if snapshot.duration_ms
            else ""
        )

        rec = assessment.recommendation
        if rec:
            self.rec_badge.setText(f"{rec.confidence.upper()} CONFIDENCE")
            self.rec_badge.setStyleSheet(
                f"color: {PALETTE['cyan']}; background: {rgba(PALETTE['cyan'], 0.10)};"
                f" border: 1px solid {rgba(PALETTE['cyan'], 0.36)}; border-radius: 7px; padding: 1px 7px;"
            )
            self.rec_channel.setText(str(rec.channel))
            self.rec_channel_unit.setVisible(True)
            self.rec_freq.setText(f"{rec.frequency_mhz} MHz \u2022 centre frequency")
            self.rec_confidence.setText(f"CONFIDENCE \u2014 {rec.confidence.upper()}")
            self.rec_meter.set_value(rec.confidence_pct, PALETTE["cyan"])
            self.rec_reason.setText(rec.reason)
            alternatives = " \u2022 ".join(f"ch {ch}" for ch in rec.alternatives[:3])
            self.rec_alt.setText(f"Alternatives: {alternatives}" if alternatives else "")
        else:
            self.rec_badge.setText("NO DATA")
            self.rec_channel.setText("\u2014")
            self.rec_channel_unit.setVisible(False)
            self.rec_freq.setText("no channel scored yet")
            self.rec_confidence.setText("CONFIDENCE \u2014")
            self.rec_meter.set_value(0)
            self.rec_reason.setText("Complete a scan to score every channel in this band.")
            self.rec_alt.setText("")

        density = assessment.congestion_pct
        density_color = (
            PALETTE["green"] if density < 25 else PALETTE["yellow"] if density < 50 else PALETTE["orange"] if density < 75 else PALETTE["red"]
        )
        self.density_badge.setText(f"{density:.0f}%")
        self.density_badge.setStyleSheet(
            f"color: {density_color}; background: {rgba(density_color, 0.10)};"
            f" border: 1px solid {rgba(density_color, 0.36)}; border-radius: 7px; padding: 1px 7px;"
        )
        self.density_meter.set_value(density, density_color)
        self.busiest.set_value(f"ch {assessment.busiest_channel}" if assessment.busiest_channel else "\u2014")
        self.quietest.set_value(f"ch {assessment.quietest_channel}" if assessment.quietest_channel else "\u2014")
        self.pairs.set_value(str(assessment.overlapping_pairs))

        data = channels.recommend_channel(band, snapshot.by_band(band), self.ctx.analysis.region)
        raw = data["scored"] if data else []
        peak = max((score for _, score in raw), default=0.0)
        scored = [(channel, (score / peak) if peak > 0 else 0.0) for channel, score in raw]
        self.interference.set_data(scored, band, rec.channel if rec else None)
        self._fill_table(assessment, scored, rec.channel if rec else None)

        self.insights_badge.setText(str(len(insights)))
        self._fill_insights(insights)
        self.export_button.setEnabled(True)

    def _render_empty(self, band: Band) -> None:
        self.rec_badge.setText("WAITING")
        self.rec_channel.setText("\u2014")
        self.rec_reason.setText("Waiting for the first scan of this band.")
        self.density_badge.setText("0%")
        self.density_meter.set_value(0, PALETTE["muted"])
        self.interference.set_data([], band, None)
        self.table.clear_rows()
        self.table.empty_note("No scans recorded yet \u2014 start monitoring to score channels")
        self._fill_insights([])
        self.export_button.setEnabled(False)

    def _fill_table(self, assessment, scored, recommended: int | None) -> None:
        score_map = {channel: score for channel, score in scored}
        counts = assessment.counts
        self.table.setRowCount(0)
        rows = 0
        for channel in sorted(score_map):
            score = score_map[channel]
            count = counts.get(channel, 0)
            if score <= 0.002 and count == 0 and channel != recommended:
                continue
            verdict = self._verdict(score, count)
            color = self._verdict_color(score)
            channel_color = PALETTE["cyan"] if channel == recommended else PALETTE["text"]
            self.table.append_row(
                [
                    str(channel),
                    f"{channels.channel_to_freq(self._band, channel)} MHz",
                    str(count),
                    f"{score:.2f}",
                    verdict,
                ],
                colors={0: channel_color, 2: PALETTE["text_secondary"], 4: color},
            )
            rows += 1
        if rows == 0:
            self.table.empty_note("No candidate channels for this band")
        self.table_badge.setText(f"{rows} CHANNELS")

    @staticmethod
    def _verdict(score: float, count: int) -> str:
        if score <= 0.02 and count == 0:
            return "clear"
        if score < 0.15:
            return "light overlap"
        if score < 0.40:
            return "moderate overlap"
        if score < 0.65:
            return "high overlap"
        return "severe overlap"

    @staticmethod
    def _verdict_color(score: float) -> str:
        if score < 0.15:
            return PALETTE["green"]
        if score < 0.40:
            return PALETTE["cyan"]
        if score < 0.65:
            return PALETTE["yellow"]
        if score < 0.85:
            return PALETTE["orange"]
        return PALETTE["red"]

    def _fill_insights(self, insights: list[Insight]) -> None:
        while self.insight_rows.count():
            item = self.insight_rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not insights:
            self.insight_rows.addWidget(
                label(
                    "Insights appear after the first completed scan of this band.",
                    9.3,
                    PALETTE["muted"],
                    400,
                    0.1,
                    wrap=True,
                )
            )
            self.insight_rows.addStretch(1)
            return
        for insight in insights:
            color = {
                "critical": PALETTE["red"],
                "warning": PALETTE["orange"],
                "good": PALETTE["green"],
            }.get(insight.severity, PALETTE["cyan"])
            self.insight_rows.addWidget(InsightDetailRow(insight, color))
        self.insight_rows.addStretch(1)

    # ------------------------------------------------------------------
    def _export(self) -> None:
        if self._snapshot is None:
            return
        try:
            path = self.ctx.reports.export_html(self._snapshot, self._assessment, self._insights)
        except Exception as exc:  # noqa: BLE001 - surface export problems in the UI
            self.notice.show_message(f"Report export failed: {exc}", "error", "Open Settings")
            try:
                self.notice.action_triggered.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.notice.action_triggered.connect(lambda: bus.navigate.emit("settings"))
        else:
            self.notice.show_message(f"HTML report saved to {path}", "good", "Open History")
            try:
                self.notice.action_triggered.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.notice.action_triggered.connect(lambda: bus.navigate.emit("history"))
        self.notice.setVisible(True)
