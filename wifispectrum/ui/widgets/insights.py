"""Spectrum Insights panel: the three highest-priority observations.

The full list lives on the Channel Analyzer page; this dashboard panel keeps a
fixed, non-scrolling set of rows so the layout never collapses or clips.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from ...core.constants import PALETTE, SEVERITY_COLORS
from ...core.models import Insight
from .. import icons
from .base import Badge, Panel, hline, label

MAX_ROWS = 3


class InsightRow(QWidget):
    """Compact two-line insight: severity dot + title, then the key metric."""

    def __init__(self, insight: Insight, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = SEVERITY_COLORS.get(insight.severity, PALETTE["cyan"])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)
        dot = QWidget()
        dot.setFixedSize(7, 7)
        dot.setStyleSheet(f"background: {self._color}; border-radius: 3px;")
        head.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        title = label(insight.title, 9.6, PALETTE["text"], 600, 0.05)
        title.setWordWrap(False)
        head.addWidget(title, 1)
        layout.addLayout(head)

        meta_text = insight.measurement or insight.detail
        meta = label(meta_text, 8.3, self._color if insight.measurement else PALETTE["muted"], 500, 0.05)
        meta.setContentsMargins(13, 0, 0, 0)
        meta.setWordWrap(False)
        layout.addWidget(meta)

        self.setToolTip(f"{insight.title}\n{insight.detail}" + (f"\n{insight.measurement}" if insight.measurement else ""))
        self.setFixedHeight(34)


class InsightsPanel(Panel):
    analyze_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Spectrum Insights", "AUTO-GENERATED", parent)
        self._signature: tuple = ()

        self.count_badge = Badge("0")
        self.count_badge.setToolTip("Total insights generated for this band")
        self.add_action(self.count_badge)

        self.rows = QVBoxLayout()
        self.rows.setContentsMargins(0, 1, 0, 0)
        self.rows.setSpacing(5)
        self.body.addLayout(self.rows, 1)

        self.empty = label(
            "Insights appear after the first completed scan.",
            9.4,
            PALETTE["muted"],
            400,
            0.1,
            wrap=True,
        )
        self.rows.addWidget(self.empty)
        self.rows.addStretch(1)

        self.analyze_button = QPushButton("  Run Channel Analyzer")
        self.analyze_button.setObjectName("Primary")
        self.analyze_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analyze_button.setFixedHeight(30)
        self.analyze_button.setIcon(icons.icon("target", "#04121F", 14))
        self.analyze_button.clicked.connect(self.analyze_requested.emit)
        self.body.addWidget(self.analyze_button)

    def set_insights(self, insights: list[Insight]) -> None:
        signature = tuple((i.severity, i.title, i.measurement) for i in insights[:MAX_ROWS])
        self.count_badge.setText(str(len(insights)))
        if signature == self._signature:
            return
        self._signature = signature

        while self.rows.count():
            item = self.rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not insights:
            self.empty = label(
                "Insights appear after the first completed scan.",
                9.4,
                PALETTE["muted"],
                400,
                0.1,
                wrap=True,
            )
            self.rows.addWidget(self.empty)
            self.rows.addStretch(1)
            return

        for index, insight in enumerate(insights[:MAX_ROWS]):
            if index:
                self.rows.addWidget(hline())
            self.rows.addWidget(InsightRow(insight))
        self.rows.addStretch(1)
        self.count_badge.setToolTip(
            f"Showing {min(len(insights), MAX_ROWS)} of {len(insights)} insights \u2014 "
            "open Channel Analyzer for the full list"
        )
