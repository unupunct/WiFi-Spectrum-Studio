"""Detected Networks table (model + delegate) used across pages."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QTableView,
    QWidget,
)

from ...core.constants import PALETTE, rssi_color, rssi_quality
from ...core.models import AccessPoint
from ...services.spectrum_service import assign_colors
from ..theme import font, mono_family
from .base import rgba

COLUMNS = ["SSID", "BSSID", "VENDOR", "SIGNAL", "CH", "BAND", "SECURITY"]
BSSID_COLUMN = 1
VENDOR_COLUMN = 2
SIGNAL_COLUMN = 3
CHANNEL_COLUMN = 4
BAND_COLUMN = 5
SECURITY_COLUMN = 6


class NetworkTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._aps: list[AccessPoint] = []
        self.colors: dict[str, str] = {}

    def set_aps(self, aps: list[AccessPoint], limit: int | None = None, sort_by: str = "signal") -> None:
        self.beginResetModel()
        keys = {
            "signal": lambda ap: (-ap.rssi, ap.display_ssid.lower()),
            "channel": lambda ap: (ap.band.value, ap.channel, -ap.rssi),
            "ssid": lambda ap: (ap.display_ssid.lower(), -ap.rssi),
            "band": lambda ap: (ap.band.value, -ap.rssi),
            "security": lambda ap: (ap.security.lower(), -ap.rssi),
        }
        ordered = sorted(aps, key=keys.get(sort_by, keys["signal"]))
        self._aps = ordered[:limit] if limit else ordered
        self.colors = assign_colors(aps)
        self.endResetModel()

    def aps(self) -> list[AccessPoint]:
        return list(self._aps)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._aps)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if section <= VENDOR_COLUMN:
                return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._aps):
            return None
        ap = self._aps[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return ap.display_ssid
            if index.column() == BSSID_COLUMN:
                return ap.bssid
            if index.column() == VENDOR_COLUMN:
                return ap.vendor
            if index.column() == SIGNAL_COLUMN:
                return f"{ap.rssi} dBm"
            if index.column() == CHANNEL_COLUMN:
                return str(ap.channel)
            if index.column() == BAND_COLUMN:
                return ap.band.short
            return ap.security
        if role == Qt.ItemDataRole.UserRole:
            return ap.bssid
        if role == Qt.ItemDataRole.ToolTipRole:
            return (
                f"{ap.display_ssid}\n{ap.bssid}\nChannel {ap.channel} \u2022 {ap.frequency_mhz} MHz "
                f"\u2022 {ap.width_mhz} MHz\n{ap.rssi} dBm \u2022 {ap.security}\n{ap.vendor}"
            )
        return None

    def ap_at(self, row: int) -> AccessPoint | None:
        if 0 <= row < len(self._aps):
            return self._aps[row]
        return None


class NetworkDelegate(QStyledItemDelegate):
    def __init__(self, model: NetworkTableModel, parent=None):
        super().__init__(parent)
        self._model = model
        self.hover_row = -1

    def sizeHint(self, option, index) -> QSize:
        return QSize(60, 28)

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        ap = self._model.ap_at(index.row())
        if ap is None:
            painter.restore()
            return

        rect = QRectF(option.rect)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = index.row() == self.hover_row
        if selected:
            painter.fillRect(rect, QColor(rgba(PALETTE["cyan"], 0.10)))
        elif hovered:
            painter.fillRect(rect, QColor(rgba(PALETTE["cyan"], 0.045)))

        column = index.column()
        if column == 0:
            color = self._model.colors.get(ap.bssid, PALETTE["cyan"])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(rect.left() + 10, rect.center().y()), 3.4, 3.4)
            painter.setFont(font(10.5, 500 if not selected else 600))
            painter.setPen(QColor(PALETTE["text"] if (selected or hovered) else PALETTE["text_secondary"]))
            text_rect = QRectF(rect.left() + 20, rect.top(), rect.width() - 24, rect.height())
            text = ap.display_ssid
            metrics = painter.fontMetrics()
            elided = metrics.elidedText(text, Qt.TextElideMode.ElideRight, int(text_rect.width()))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
        elif column == BSSID_COLUMN:
            painter.setFont(QFont(mono_family(), 8))
            painter.setPen(QColor(PALETTE["muted"]))
            text_rect = QRectF(rect.left() + 2, rect.top(), rect.width() - 6, rect.height())
            elided = painter.fontMetrics().elidedText(
                ap.bssid.upper(), Qt.TextElideMode.ElideMiddle, int(text_rect.width())
            )
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
        elif column == VENDOR_COLUMN:
            painter.setFont(font(8.4, 500))
            painter.setPen(QColor(PALETTE["text_secondary"]))
            text_rect = QRectF(rect.left() + 2, rect.top(), rect.width() - 8, rect.height())
            elided = painter.fontMetrics().elidedText(
                ap.vendor, Qt.TextElideMode.ElideRight, int(text_rect.width())
            )
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
        elif column == SIGNAL_COLUMN:
            self._paint_signal(painter, rect, ap)
        elif column == CHANNEL_COLUMN:
            painter.setFont(QFont(mono_family(), 9))
            painter.setPen(QColor(PALETTE["text_secondary"]))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(ap.channel))
        elif column == BAND_COLUMN:
            painter.setFont(font(8, 600, 0.4))
            painter.setPen(QColor(ap.band.color))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, ap.band.short)
        else:
            color = {
                "Open": PALETTE["orange"],
                "WEP": PALETTE["red"],
                "WPA": PALETTE["yellow"],
            }.get(ap.security, PALETTE["text_secondary"])
            painter.setFont(font(8.5, 500))
            painter.setPen(QColor(color))
            painter.drawText(
                QRectF(rect.left(), rect.top(), rect.width() - 6, rect.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                ap.security,
            )

        painter.setPen(QPen(QColor(rgba("#17465B", 0.55)), 1))
        painter.drawLine(QPointF(rect.left(), rect.bottom()), QPointF(rect.right(), rect.bottom()))
        painter.restore()

    def _paint_signal(self, painter: QPainter, rect: QRectF, ap: AccessPoint) -> None:
        quality = rssi_quality(ap.rssi)
        filled = {"excellent": 4, "good": 3, "fair": 2, "weak": 1, "poor": 0}.get(quality, 1)
        color = rssi_color(ap.rssi)
        base_x = rect.left() + 2
        center_y = rect.center().y() + 4
        for index in range(4):
            height = 4 + index * 3
            bar = QRectF(base_x + index * 4.2, center_y - height, 2.8, height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color if index < filled else rgba(PALETTE["muted"], 0.28)))
            painter.drawRoundedRect(bar, 1.2, 1.2)
        painter.setFont(QFont(mono_family(), 8))
        painter.setPen(QColor(rssi_color(ap.rssi)))
        number = f"{ap.rssi}"
        number_width = painter.fontMetrics().horizontalAdvance(number)
        painter.drawText(
            QRectF(base_x + 19, rect.top(), number_width + 4, rect.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            number,
        )
        painter.setFont(font(7.5))
        painter.setPen(QColor(PALETTE["muted"]))
        painter.drawText(
            QRectF(base_x + 23 + number_width, rect.top(), 28, rect.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "dBm",
        )


class NetworkTable(QTableView):
    network_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None, show_band: bool = False,
                 show_meta: bool = False):
        super().__init__(parent)
        self._model = NetworkTableModel(self)
        self.setModel(self._model)
        self._delegate = NetworkDelegate(self._model, self)
        self.setItemDelegate(self._delegate)

        self.setShowGrid(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.setAlternatingRowColors(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionsClickable(False)
        header.setFixedHeight(26)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (BSSID_COLUMN, VENDOR_COLUMN, SIGNAL_COLUMN, CHANNEL_COLUMN, BAND_COLUMN, SECURITY_COLUMN):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(BSSID_COLUMN, 122)
        header.resizeSection(VENDOR_COLUMN, 146)
        header.resizeSection(SIGNAL_COLUMN, 92)
        header.resizeSection(CHANNEL_COLUMN, 38)
        header.resizeSection(BAND_COLUMN, 52)
        header.resizeSection(SECURITY_COLUMN, 74)
        self.setColumnHidden(BAND_COLUMN, not show_band)
        self.setColumnHidden(BSSID_COLUMN, not show_meta)
        self.setColumnHidden(VENDOR_COLUMN, not show_meta)

        self.clicked.connect(self._on_clicked)
        self.entered.connect(self._on_entered)

    def set_show_band(self, show: bool) -> None:
        self.setColumnHidden(BAND_COLUMN, not show)

    def set_show_meta(self, show: bool) -> None:
        self.setColumnHidden(BSSID_COLUMN, not show)
        self.setColumnHidden(VENDOR_COLUMN, not show)

    def set_aps(self, aps: list[AccessPoint], limit: int | None = None, sort_by: str = "signal") -> None:
        self._model.set_aps(aps, limit, sort_by)
        self._delegate.hover_row = -1
        self.viewport().update()

    def model(self) -> NetworkTableModel:  # type: ignore[override]
        return self._model

    def _on_clicked(self, index) -> None:
        ap = self._model.ap_at(index.row())
        if ap:
            self.network_selected.emit(ap.bssid)

    def _on_entered(self, index) -> None:
        row = index.row()
        if row != self._delegate.hover_row:
            self._delegate.hover_row = row
            self.viewport().update()

    def leaveEvent(self, event) -> None:
        self._delegate.hover_row = -1
        self.viewport().update()
        super().leaveEvent(event)
