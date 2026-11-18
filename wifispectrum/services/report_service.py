"""Report generation: HTML, CSV, JSON and PDF (via Qt's PDF writer)."""

from __future__ import annotations

import csv
import html
import json
import logging
import time
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

from ..core import channels
from ..core.constants import APP_NAME, APP_VERSION, rssi_color
from ..core.models import Band, ChannelAssessment, Insight, ScanSnapshot

log = logging.getLogger(__name__)


class ReportError(RuntimeError):
    pass


def _fmt_ts(ts: float | None = None) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts or time.time()))


class ReportService:
    def __init__(self, export_dir: str):
        self.export_dir = Path(export_dir)

    # -- helpers -----------------------------------------------------------
    def _target(self, name: str) -> Path:
        try:
            self.export_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ReportError(f"Export directory is not writable: {exc}") from exc
        return self.export_dir / name

    @staticmethod
    def _stamp() -> str:
        return time.strftime("%Y%m%d-%H%M%S")

    # -- data exports ------------------------------------------------------
    def export_json(
        self,
        snapshot: ScanSnapshot,
        assessment: ChannelAssessment | None = None,
        insights: list[Insight] | None = None,
        path: str | Path | None = None,
    ) -> str:
        target = Path(path) if path else self._target(f"spectrum-report-{self._stamp()}.json")
        payload = {
            "application": APP_NAME,
            "version": APP_VERSION,
            "generated_at": _fmt_ts(),
            "data_source": {
                "backend": snapshot.backend,
                "demo": snapshot.demo,
                "adapter": snapshot.adapter.to_dict() if snapshot.adapter else None,
            },
            "scan": {
                "timestamp": snapshot.timestamp,
                "duration_ms": round(snapshot.duration_ms, 2),
                "total_networks": snapshot.total,
            },
            "assessment": None,
            "insights": [insight.__dict__ for insight in (insights or [])],
            "networks": [
                {
                    "ssid": ap.ssid,
                    "bssid": ap.bssid,
                    "channel": ap.channel,
                    "frequency_mhz": ap.frequency_mhz,
                    "band": ap.band.label,
                    "width_mhz": ap.width_mhz,
                    "rssi_dbm": ap.rssi,
                    "security": ap.security,
                    "vendor": ap.vendor,
                    "phy": ap.phy,
                }
                for ap in snapshot.aps
            ],
        }
        if assessment:
            payload["assessment"] = {
                "band": assessment.band.label,
                "congestion_pct": assessment.congestion_pct,
                "observations": assessment.observations,
                "overlapping_pairs": assessment.overlapping_pairs,
                "channel_counts": {str(k): v for k, v in assessment.counts.items()},
                "recommendation": (
                    {
                        "channel": assessment.recommendation.channel,
                        "frequency_mhz": assessment.recommendation.frequency_mhz,
                        "reason": assessment.recommendation.reason,
                        "confidence": assessment.recommendation.confidence,
                        "score": assessment.recommendation.score,
                    }
                    if assessment.recommendation
                    else None
                ),
            }
        try:
            target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            raise ReportError(f"Could not write JSON report: {exc}") from exc
        return str(target)

    def export_csv(self, snapshot: ScanSnapshot, path: str | Path | None = None) -> str:
        target = Path(path) if path else self._target(f"spectrum-networks-{self._stamp()}.csv")
        try:
            with target.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "ssid", "bssid", "vendor", "channel", "frequency_mhz", "band",
                        "width_mhz", "rssi_dbm", "security", "phy", "first_seen", "last_seen",
                    ]
                )
                for ap in snapshot.aps:
                    writer.writerow(
                        [
                            ap.ssid, ap.bssid, ap.vendor, ap.channel, ap.frequency_mhz, ap.band.label,
                            ap.width_mhz, ap.rssi, ap.security, ap.phy,
                            _fmt_ts(ap.first_seen), _fmt_ts(ap.last_seen),
                        ]
                    )
        except OSError as exc:
            raise ReportError(f"Could not write CSV export: {exc}") from exc
        return str(target)

    # -- HTML --------------------------------------------------------------
    def export_html(
        self,
        snapshot: ScanSnapshot,
        assessment: ChannelAssessment | None,
        insights: list[Insight],
        path: str | Path | None = None,
    ) -> str:
        target = Path(path) if path else self._target(f"spectrum-report-{self._stamp()}.html")
        document = self._html_document(snapshot, assessment, insights, print_mode=False)
        try:
            target.write_text(document, encoding="utf-8")
        except OSError as exc:
            raise ReportError(f"Could not write HTML report: {exc}") from exc
        return str(target)

    def export_pdf(
        self,
        snapshot: ScanSnapshot,
        assessment: ChannelAssessment | None,
        insights: list[Insight],
        path: str | Path | None = None,
    ) -> str:
        target = Path(path) if path else self._target(f"spectrum-report-{self._stamp()}.pdf")
        document_html = self._html_document(snapshot, assessment, insights, print_mode=True)
        try:
            writer = QPdfWriter(str(target))
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setPageMargins(QMarginsF(14, 14, 14, 14), QPageLayout.Unit.Millimeter)
            writer.setResolution(110)
            writer.setTitle(f"{APP_NAME} report")
            doc = QTextDocument()
            doc.setDocumentMargin(0)
            doc.setHtml(document_html)
            doc.setPageSize(QSizeF(writer.width(), writer.height()))
            doc.print_(writer)
        except Exception as exc:  # noqa: BLE001 - Qt raises various types
            raise ReportError(f"Could not write PDF report: {exc}") from exc
        return str(target)

    # -- document builders -------------------------------------------------
    def _html_document(
        self,
        snapshot: ScanSnapshot,
        assessment: ChannelAssessment | None,
        insights: list[Insight],
        print_mode: bool,
    ) -> str:
        adapter = snapshot.adapter
        band = assessment.band if assessment else Band.GHZ_24
        counts = assessment.counts if assessment else snapshot.counts_by_channel(band)
        max_count = max(counts.values()) if counts else 1
        supported = channels.band_channels(band, "WORLD")
        rows = []
        for channel in supported:
            count = counts.get(channel, 0)
            pct = int(round(100 * count / max(1, max_count)))
            bar = (
                f'<table cellpadding="0" cellspacing="0" style="width:100%;"><tr>'
                f'<td style="background:#E4EDF5;height:10px;width:100%;">'
                f'<table cellpadding="0" cellspacing="0" style="width:{pct}%;"><tr>'
                f'<td style="background:#00A8C6;height:10px;">&nbsp;</td></tr></table>'
                f"</td></tr></table>"
            )
            rows.append(
                f'<tr><td style="padding:3px 8px;color:#33475B;font-size:8pt;">Ch {channel}</td>'
                f'<td style="padding:3px 8px;color:#0B2233;font-size:8pt;font-weight:bold;">{count}</td>'
                f'<td style="padding:3px 4px;width:46%;">{bar}</td></tr>'
            )
        channel_table = "".join(rows) or '<tr><td style="padding:6px;color:#6A7C8C;">No data</td></tr>'

        insight_items = "".join(
            f'<tr><td style="width:6px;background:{self._severity_color(i.severity)};">&nbsp;</td>'
            f'<td style="padding:5px 9px;font-family:Arial;font-size:9pt;color:#0B2233;">'
            f'<b>{html.escape(i.title)}</b><br><span style="color:#4A6172;font-size:8pt;">'
            f"{html.escape(i.detail)} &nbsp;|&nbsp; {html.escape(i.measurement)}</span></td></tr>"
            for i in insights
        ) or '<tr><td style="padding:6px;color:#6A7C8C;">No insights recorded.</td></tr>'

        network_rows = "".join(
            f"<tr>"
            f'<td style="padding:4px 6px;font-size:8pt;color:#0B2233;">{html.escape(ap.ssid)}</td>'
            f'<td style="padding:4px 6px;font-size:8pt;color:#4A6172;font-family:Consolas,monospace;">{ap.bssid}</td>'
            f'<td style="padding:4px 6px;font-size:8pt;color:#0B2233;text-align:center;">{ap.channel}</td>'
            f'<td style="padding:4px 6px;font-size:8pt;color:#0B2233;text-align:center;">{ap.width_mhz} MHz</td>'
            f'<td style="padding:4px 6px;font-size:8pt;color:{rssi_color(ap.rssi)};text-align:right;">{ap.rssi} dBm</td>'
            f'<td style="padding:4px 6px;font-size:8pt;color:#0B2233;">{html.escape(ap.security)}</td>'
            f"</tr>"
            for ap in sorted(snapshot.aps, key=lambda a: a.rssi, reverse=True)[:40]
        ) or '<tr><td colspan="6" style="padding:6px;color:#6A7C8C;">No networks observed.</td></tr>'

        rec = assessment.recommendation if assessment else None
        rec_block = ""
        if rec:
            rec_block = (
                f'<table cellpadding="0" cellspacing="0" style="width:100%;background:#F2FAFD;'
                f'border-left:3px solid #00A8C6;margin:8px 0;"><tr>'
                f'<td style="padding:10px 12px;font-family:Arial;font-size:9pt;color:#0B2233;">'
                f"<b>Recommended channel:</b> {rec.channel} &nbsp;({rec.frequency_mhz} MHz) &nbsp; "
                f'<span style="color:#4A6172;">confidence {rec.confidence}</span><br>'
                f'<span style="color:#4A6172;font-size:8pt;">{html.escape(rec.reason)}</span>'
                f"</td></tr></table>"
            )

        demo_banner = (
            '<table cellpadding="0" cellspacing="0" style="width:100%;background:#FFF4D6;'
            'border-left:3px solid #D89B00;margin:6px 0;"><tr><td style="padding:7px 11px;'
            'font-family:Arial;font-size:8pt;color:#7A5200;"><b>DEMO DATA</b> &mdash; these '
            "observations are simulated and must not be treated as measurements.</td></tr></table>"
            if snapshot.demo
            else ""
        )

        strongest = max(snapshot.aps, key=lambda a: a.rssi) if snapshot.aps else None
        tiles = [
            ("Access Points", str(snapshot.total)),
            ("Active Band", band.label),
            ("Strongest Signal", f"{strongest.rssi} dBm" if strongest else "\u2014"),
            ("Channels In Use", str(len(counts))),
            ("Congestion Estimate", f"{assessment.congestion_pct:.0f}%" if assessment else "\u2014"),
        ]
        tile_cells = "".join(
            f'<td style="padding:9px 11px;border:1px solid #DCE7EF;background:#F7FBFE;">'
            f'<div style="font-family:Arial;font-size:7.5pt;color:#6A7C8C;letter-spacing:1px;">{label.upper()}</div>'
            f'<div style="font-family:Arial;font-size:15pt;font-weight:bold;color:#0B2233;">{value}</div></td>'
            for label, value in tiles
        )

        adapter_line = (
            f"{adapter.interface} &middot; {html.escape(adapter.name)} &middot; driver "
            f"{html.escape(adapter.driver)} &middot; bands {adapter.band_labels}"
            if adapter
            else "No adapter information available"
        )

        source = "Simulated (demo)" if snapshot.demo else f"Live scan via {snapshot.backend}"
        css = """
        body { font-family: Arial, Helvetica, sans-serif; color:#0B2233; background:#FFFFFF; margin:0; }
        .wrap { padding: 0; }
        .h1 { font-size: 20pt; font-weight: bold; letter-spacing: 0.4px; color:#0B2233; }
        .sub { font-size: 8.5pt; color:#5C7284; }
        .kicker { font-size: 7.5pt; letter-spacing: 2px; color:#00A8C6; font-weight: bold; }
        .rule { height: 2px; background:#00A8C6; }
        .section { font-size: 9pt; font-weight:bold; letter-spacing:1.6px; color:#22475C; margin:14px 0 6px 0; }
        table.data { width:100%; border-collapse: collapse; }
        table.data th { text-align:left; font-size:7.5pt; color:#6A7C8C; letter-spacing:1px; padding:4px 6px; border-bottom:1px solid #DCE7EF; }
        table.data td { border-bottom:1px solid #EEF3F7; }
        """
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{APP_NAME} report</title><style>{css}</style></head>
<body><div class="wrap">
<table cellpadding="0" cellspacing="0" style="width:100%;"><tr>
<td style="width:6px;background:#00A8C6;">&nbsp;</td>
<td style="padding:2px 0 2px 12px;">
<div class="kicker">WIFI SPECTRUM STUDIO</div>
<div class="h1">Wireless Spectrum Report</div>
<div class="sub">Generated {_fmt_ts()} &nbsp;&middot;&nbsp; {source} &nbsp;&middot;&nbsp; {APP_VERSION}</div>
</td></tr></table>
<div class="rule" style="margin:10px 0 2px 0;"></div>
<table cellpadding="0" cellspacing="0" style="width:100%;margin-top:10px;"><tr>
<td style="font-size:8pt;color:#5C7284;">{adapter_line}</td></tr></table>
{demo_banner}
<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:separate;border-spacing:5px 0;"><tr>{tile_cells}</tr></table>
{rec_block}
<div class="section">SPECTRUM INSIGHTS</div>
<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;">{insight_items}</table>
<div class="section">CHANNEL DISTRIBUTION &mdash; {band.label}</div>
<table cellpadding="0" cellspacing="0" class="data"><tr>
<th style="width:16%;">CHANNEL</th><th style="width:10%;">APS</th><th>RELATIVE DENSITY</th></tr>
{channel_table}</table>
<div class="section">DETECTED NETWORKS</div>
<table cellpadding="0" cellspacing="0" class="data">
<tr><th>SSID</th><th>BSSID</th><th style="text-align:center;">CH</th><th style="text-align:center;">WIDTH</th>
<th style="text-align:right;">SIGNAL</th><th>SECURITY</th></tr>
{network_rows}</table>
<div style="margin-top:14px;font-size:7pt;color:#8A9AA8;line-height:1.5;">
Scan-derived visualisation. Channel counts are network density indicators, not airtime utilisation.
Spectrum curves are channel-shaped representations built from observed channel, width and RSSI values.
Continuous FFT spectrum requires compatible SDR hardware.
</div>
</div></body></html>"""

    @staticmethod
    def _severity_color(severity: str) -> str:
        return {
            "critical": "#E0455F",
            "warning": "#D89B00",
            "good": "#00A57B",
            "info": "#00A8C6",
        }.get(severity, "#00A8C6")
