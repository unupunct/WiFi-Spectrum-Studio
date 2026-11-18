"""Lightweight styled table used by the analysis, history and discovery pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ..theme import font, mono_family


class DataTable(QTableWidget):
    def __init__(
        self,
        headers: list[str],
        parent: QWidget | None = None,
        row_height: int = 28,
        stretch_column: int = 0,
        mono_columns: tuple[int, ...] = (),
        widths: dict[int, int] | None = None,
    ):
        super().__init__(0, len(headers), parent)
        self._mono_columns = set(mono_columns)
        self._stretch_column = stretch_column
        self.setHorizontalHeaderLabels(headers)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(row_height)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setAlternatingRowColors(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionsClickable(False)
        header.setFixedHeight(26)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        if 0 <= stretch_column < len(headers):
            header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)
        for column in mono_columns:
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(column, 76)
        for column, width in (widths or {}).items():
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(column, width)

        # QTableWidget paints header items from its item model, so the stretch
        # column's alignment must be set on the item itself.
        header_item = self.horizontalHeaderItem(stretch_column)
        if header_item is not None:
            header_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

    # -- population --------------------------------------------------------
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.TextAlignmentRole:
                if section == self._stretch_column:
                    return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                return int(Qt.AlignmentFlag.AlignCenter)
        return super().headerData(section, orientation, role)

    def set_rows(self, rows: list[list[str]]) -> None:
        self.clearSpans()
        self.setRowCount(0)
        for values in rows:
            self.append_row(values)

    def append_row(self, values: list[str], colors: dict[int, str] | None = None,
                   align: dict[int, Qt.AlignmentFlag] | None = None) -> None:
        row = self.rowCount()
        self.insertRow(row)
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if column in self._mono_columns:
                item.setFont(QFont(mono_family(), 8))
            if colors and column in colors:
                item.setForeground(QColor(colors[column]))
            if align and column in align:
                item.setTextAlignment(align[column])
            self.setItem(row, column, item)

    def row_values(self, row: int) -> list[str]:
        return [self.item(row, c).text() if self.item(row, c) else "" for c in range(self.columnCount())]

    def empty_note(self, text: str) -> None:
        self.clearSpans()
        self.setRowCount(1)
        self.setSpan(0, 0, 1, self.columnCount())
        item = QTableWidgetItem(text)
        item.setForeground(QColor("#647F91"))
        item.setFont(font(10))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(0, 0, item)

    def clear_rows(self) -> None:
        self.clearSpans()
        self.setRowCount(0)
