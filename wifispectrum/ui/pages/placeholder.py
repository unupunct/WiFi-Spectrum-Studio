"""Temporary placeholder page used while modules are being built."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ...core.constants import PALETTE
from ..widgets.base import EmptyState, Panel, label


class PlaceholderPage(QWidget):
    def __init__(self, title: str, detail: str = "This module is being connected.", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        heading = label(title, 17, PALETTE["text"], 600, 0.2)
        layout.addWidget(heading)
        subtitle = label(detail, 9.5, PALETTE["muted"], 400, 0.1)
        layout.addWidget(subtitle)
        panel = Panel(title, "MODULE STATUS")
        panel.add(
            EmptyState(
                "layers",
                "Module not yet wired",
                "This page is part of the incremental build and will be connected to live data.",
            ),
            1,
        )
        layout.addWidget(panel, 1)
