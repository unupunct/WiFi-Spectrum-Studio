"""Right-hand network inspection drawer."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import PALETTE, rssi_color, rssi_quality
from ...core.models import AccessPoint
from .. import icons
from ..theme import font, mono_family
from .base import Badge, IconButton, KeyValueRow, hline, label, rgba


class NetworkDetailDrawer(QFrame):
    track_requested = Signal(str)
    closed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Drawer")
        self.setStyleSheet(
            "QFrame#Drawer { background: #0A1A28; border-left: 1px solid #1E6A82; }"
        )
        self.setFixedWidth(360)
        self.setVisible(False)
        self._ap: AccessPoint | None = None
        self._bssid = ""

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(34)
        shadow.setOffset(-8, 0)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        kicker = label("NETWORK INSPECTION", 7.5, PALETTE["cyan"], 600, 1.6)
        head.addWidget(kicker)
        head.addStretch(1)
        self.close_button = IconButton("close", "Close (Esc)", 24, 13)
        self.close_button.clicked.connect(self.hide_drawer)
        head.addWidget(self.close_button)
        layout.addLayout(head)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self.ssid = label("\u2014", 16, PALETTE["text"], 600, 0.1)
        self.ssid.setWordWrap(True)
        title_row.addWidget(self.ssid, 1)
        self.band_badge = Badge("2.4 GHZ", PALETTE["green"])
        title_row.addWidget(self.band_badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(title_row)

        self.bssid = label("\u2014", 9, PALETTE["muted"], 400, 0.3)
        self.bssid.setFont(self._mono(9))
        layout.addWidget(self.bssid)

        signal_frame = QFrame()
        signal_frame.setObjectName("Inset")
        signal_layout = QHBoxLayout(signal_frame)
        signal_layout.setContentsMargins(12, 10, 12, 10)
        signal_layout.setSpacing(10)
        self.rssi_value = label("\u2014", 24, PALETTE["text"], 600, 0.2)
        sig_col = QVBoxLayout()
        sig_col.setSpacing(0)
        sig_col.addWidget(self.rssi_value)
        sig_col.addWidget(label("OBSERVED SIGNAL", 7.5, PALETTE["muted"], 600, 1.1))
        signal_layout.addLayout(sig_col)
        signal_layout.addStretch(1)
        self.quality = Badge("UNKNOWN", PALETTE["muted"])
        signal_layout.addWidget(self.quality, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(signal_frame)

        layout.addWidget(label("LINK DETAILS", 7.5, PALETTE["muted"], 600, 1.4))

        self.rows = {
            "channel": KeyValueRow("Channel"),
            "frequency": KeyValueRow("Center frequency"),
            "width": KeyValueRow("Channel width"),
            "security": KeyValueRow("Security"),
            "vendor": KeyValueRow("Vendor (OUI)"),
            "phy": KeyValueRow("PHY"),
            "first": KeyValueRow("First detected"),
            "last": KeyValueRow("Last detected"),
            "source": KeyValueRow("Data source"),
        }
        for row in self.rows.values():
            layout.addWidget(row)

        layout.addWidget(hline())
        layout.addWidget(label("ACTIONS", 7.5, PALETTE["muted"], 600, 1.4))

        self.track_button = QPushButton("  Track signal")
        self.track_button.setObjectName("Primary")
        self.track_button.setIcon(icons.icon("signal", "#04121F", 14))
        self.track_button.setFixedHeight(30)
        self.track_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.track_button.clicked.connect(self._track)
        layout.addWidget(self.track_button)

        secondary = QHBoxLayout()
        secondary.setSpacing(8)
        self.copy_button = QPushButton("  Copy BSSID")
        self.copy_button.setObjectName("Ghost")
        self.copy_button.setFixedHeight(28)
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.clicked.connect(self._copy)
        secondary.addWidget(self.copy_button)
        self.close_secondary = QPushButton("Close")
        self.close_secondary.setObjectName("Ghost")
        self.close_secondary.setFixedHeight(28)
        self.close_secondary.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_secondary.clicked.connect(self.hide_drawer)
        secondary.addWidget(self.close_secondary)
        layout.addLayout(secondary)

        layout.addStretch(1)
        self.footer = label(
            "Values are the latest scan observations. Hover the spectrum graph for a quick readout.",
            8,
            PALETTE["muted"],
            400,
            0.1,
            wrap=True,
        )
        layout.addWidget(self.footer)

        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @staticmethod
    def _mono(size: int):
        f = font(size, 400, 0.3)
        f.setFamily(mono_family())
        return f

    # -- API ---------------------------------------------------------------
    def show_for(self, ap: AccessPoint) -> None:
        self._ap = ap
        self._bssid = ap.bssid
        self.set_network(ap)
        if not self.isVisible():
            self.setVisible(True)
            self.reposition()
            parent = self.parentWidget()
            if parent:
                start = parent.width()
                self.move(start, 0)
                self._anim.stop()
                self._anim.setStartValue(self.pos())
                self._anim.setEndValue(self._end_pos())
                self._anim.start()
        self.raise_()

    def set_network(self, ap: AccessPoint) -> None:
        self._ap = ap
        self._bssid = ap.bssid
        self.ssid.setText(ap.display_ssid)
        band = ap.band
        self.band_badge.setText(band.label.upper())
        self.band_badge.setStyleSheet(
            f"color: {band.color}; background: {rgba(band.color, 0.10)};"
            f" border: 1px solid {rgba(band.color, 0.36)}; border-radius: 7px; padding: 1px 7px;"
        )
        self.bssid.setText(ap.bssid.upper())
        self.rssi_value.setText(f"{ap.rssi} dBm")
        self.rssi_value.setStyleSheet(f"color: {rssi_color(ap.rssi)}; background: transparent;")
        quality = rssi_quality(ap.rssi)
        color = rssi_color(ap.rssi)
        self.quality.setText(quality.upper())
        self.quality.setStyleSheet(
            f"color: {color}; background: {rgba(color, 0.10)}; border: 1px solid {rgba(color, 0.36)};"
            f" border-radius: 7px; padding: 1px 7px;"
        )
        import time

        self.rows["channel"].set_value(str(ap.channel))
        self.rows["frequency"].set_value(f"{ap.frequency_mhz} MHz")
        self.rows["width"].set_value(f"{ap.width_mhz} MHz")
        self.rows["security"].set_value(ap.security)
        self.rows["vendor"].set_value(ap.vendor)
        self.rows["phy"].set_value(ap.phy or "802.11")
        self.rows["first"].set_value(time.strftime("%H:%M:%S", time.localtime(ap.first_seen)))
        self.rows["last"].set_value(time.strftime("%H:%M:%S", time.localtime(ap.last_seen)))
        self.rows["source"].set_value(ap.source)

    def hide_drawer(self) -> None:
        if not self.isVisible():
            return
        self.setVisible(False)
        self.closed.emit()

    def reposition(self) -> None:
        parent = self.parentWidget()
        if not parent:
            return
        x = parent.width() - self.width()
        self.setGeometry(x, 0, self.width(), parent.height())

    def _end_pos(self):
        from PySide6.QtCore import QPoint

        parent = self.parentWidget()
        return QPoint((parent.width() if parent else 0) - self.width(), 0)

    def _track(self) -> None:
        if self._bssid:
            self.track_requested.emit(self._bssid)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self._bssid)
        self.copy_button.setText("  Copied")
        from PySide6.QtCore import QTimer

        QTimer.singleShot(1400, lambda: self.copy_button.setText("  Copy BSSID"))
