"""Application theme: palette, fonts, generated UI assets and the QSS sheet."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication, QWidget

from ..core.constants import PALETTE
from ..core.platform import config_dir

_PREFERRED_FAMILIES = ["Segoe UI", "Inter", "Cantarell", "Noto Sans", "DejaVu Sans", "Helvetica Neue", "Arial"]


def font_family() -> str:
    families = set(QFontDatabase.families())
    for candidate in _PREFERRED_FAMILIES:
        if candidate in families:
            return candidate
    return QApplication.font().family()


def mono_family() -> str:
    families = set(QFontDatabase.families())
    for candidate in ("Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "Menlo"):
        if candidate in families:
            return candidate
    return "monospace"


def font(size: int = 12, weight: int = 400, spacing: float = 0.0, italic: bool = False) -> QFont:
    f = QFont(font_family())
    f.setPixelSize(max(7, size))
    f.setWeight(QFont.Weight(weight) if weight >= 0 else QFont.Weight.Normal)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    f.setItalic(italic)
    return f


# ---------------------------------------------------------------------------
# Generated raster assets (arrow, check marks) referenced from QSS
# ---------------------------------------------------------------------------
_ASSETS: dict[str, str] = {}


def _asset_dir() -> Path:
    path = config_dir() / "ui-assets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_pixmap(px: QPixmap, name: str) -> str:
    target = _asset_dir() / name
    px.save(str(target), "PNG")
    return target.as_posix()


def _draw_chevron(color: str) -> QPixmap:
    px = QPixmap(20, 20)
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(2.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPolyline(QPolygonF([QPointF(5.4, 7.8), QPointF(10, 12.4), QPointF(14.6, 7.8)]))
    painter.end()
    return px


def _draw_check(color: str) -> QPixmap:
    px = QPixmap(18, 18)
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(2.2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPolyline(QPolygonF([QPointF(4.2, 9.4), QPointF(7.4, 12.6), QPointF(13.8, 5.4)]))
    painter.end()
    return px


def ensure_assets() -> dict[str, str]:
    if _ASSETS:
        return _ASSETS
    _ASSETS["chevron"] = _save_pixmap(_draw_chevron(PALETTE["text_secondary"]), "chevron-down.png")
    _ASSETS["chevron_cyan"] = _save_pixmap(_draw_chevron(PALETTE["cyan"]), "chevron-down-cyan.png")
    _ASSETS["check_dark"] = _save_pixmap(_draw_check("#04121F"), "check-dark.png")
    _ASSETS["check_cyan"] = _save_pixmap(_draw_check(PALETTE["cyan"]), "check-cyan.png")
    return _ASSETS


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------
def stylesheet() -> str:
    assets = ensure_assets()
    p = PALETTE
    return f"""
* {{
    outline: none;
}}
QWidget {{
    color: {p['text']};
    font-size: 12px;
    selection-background-color: rgba(0, 217, 245, 0.25);
    selection-color: {p['text']};
}}
QMainWindow, QWidget#Root, QWidget#Content, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{
    background: {p['bg']};
}}
QWidget#Sidebar {{
    background: {p['sidebar']};
    border-right: 1px solid #123246;
}}
QWidget#TopBar {{
    background: #081523;
    border-bottom: 1px solid #123246;
}}
QWidget#BottomBar {{
    background: #081523;
    border-top: 1px solid #123246;
}}
QFrame#Panel {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0E1F2E, stop:1 #0B1926);
    border: 1px solid {p['border']};
    border-radius: 12px;
}}
QFrame#PanelFlat {{
    background: {p['panel']};
    border: 1px solid #143A4E;
    border-radius: 10px;
}}
QFrame#MetricCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #102538, stop:1 #0A1826);
    border: 1px solid {p['border']};
    border-radius: 12px;
}}
QFrame#MetricCard:hover {{
    border: 1px solid #1F6F89;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #12293D, stop:1 #0B1B2A);
}}
QFrame#Inset {{
    background: #0A1826;
    border: 1px solid #123246;
    border-radius: 9px;
}}
QFrame#Divider {{
    background: #143A4E;
    max-height: 1px;
    border: none;
}}
QLabel {{
    background: transparent;
    color: {p['text']};
}}
QLabel#Muted {{
    color: {p['muted']};
}}
QLabel#Secondary {{
    color: {p['text_secondary']};
}}
QLabel#Cyan {{
    color: {p['cyan']};
}}
QLabel#PanelTitle {{
    color: {p['text']};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#PanelHint {{
    color: {p['muted']};
    font-size: 10px;
}}
QLabel#BigValue {{
    color: {p['text']};
    font-size: 23px;
    font-weight: 600;
}}
QLabel#CardLabel {{
    color: {p['text_secondary']};
    font-size: 9px;
}}
QLabel#PageTitle {{
    color: {p['text']};
    font-size: 18px;
    font-weight: 600;
}}
QLabel#EmptyState {{
    color: {p['muted']};
    font-size: 12px;
}}
QLabel#Badge {{
    background: rgba(0, 217, 245, 0.10);
    border: 1px solid rgba(0, 217, 245, 0.35);
    border-radius: 8px;
    color: {p['cyan']};
    padding: 2px 8px;
    font-size: 9px;
}}
QLabel#DemoBadge {{
    background: rgba(255, 194, 71, 0.12);
    border: 1px solid rgba(255, 194, 71, 0.45);
    border-radius: 8px;
    color: {p['yellow']};
    padding: 2px 9px;
    font-size: 9px;
    font-weight: 600;
}}
QPushButton {{
    background: #12283A;
    border: 1px solid {p['border']};
    border-radius: 8px;
    color: {p['text']};
    padding: 6px 12px;
    font-size: 11px;
}}
QPushButton:hover {{
    background: #17334A;
    border-color: #24677F;
}}
QPushButton:pressed {{
    background: #0F2333;
}}
QPushButton:disabled {{
    color: #4E6678;
    border-color: #133145;
    background: #0B1B28;
}}
QPushButton#Primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p['cyan']}, stop:1 {p['cyan_bright']});
    border: 1px solid {p['cyan']};
    color: #04121F;
    font-weight: 700;
}}
QPushButton#Primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #45E9FF, stop:1 {p['cyan']});
}}
QPushButton#Primary:disabled {{
    background: #14384A;
    border-color: #1A4A5E;
    color: #5F7D8E;
}}
QPushButton#Ghost {{
    background: transparent;
    border: 1px solid {p['border']};
    color: {p['text_secondary']};
}}
QPushButton#Ghost:hover {{
    color: {p['text']};
    border-color: {p['cyan']};
    background: rgba(0, 217, 245, 0.07);
}}
QPushButton#Ghost:checked {{
    color: {p['cyan']};
    border-color: {p['cyan']};
    background: rgba(0, 217, 245, 0.12);
}}
QPushButton#Danger {{
    background: rgba(255, 92, 122, 0.10);
    border: 1px solid rgba(255, 92, 122, 0.45);
    color: #FF8CA3;
}}
QPushButton#Link {{
    background: transparent;
    border: none;
    color: {p['cyan']};
    padding: 2px 4px;
    font-size: 10px;
}}
QPushButton#Link:hover {{
    color: #7AEEFF;
    text-decoration: underline;
}}
QPushButton#IconButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 0px;
}}
QPushButton#IconButton:hover {{
    background: rgba(0, 217, 245, 0.09);
    border-color: #1E6A82;
}}
QPushButton#IconButton:checked {{
    background: rgba(0, 217, 245, 0.14);
    border-color: {p['cyan']};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
    background: #0A1826;
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 5px 9px;
    min-height: 22px;
    color: {p['text']};
    font-size: 11px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {{
    border-color: {p['cyan']};
    background: #0B1C2B;
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    color: #5C7486;
    background: #0B1A27;
}}
QLineEdit#Search {{
    padding-left: 30px;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: url("{assets['chevron']}");
    width: 11px;
    height: 11px;
}}
QComboBox QAbstractItemView {{
    background: #0C1E2E;
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 4px;
    selection-background-color: rgba(0, 217, 245, 0.16);
    selection-color: {p['text']};
    outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 14px;
    border: none;
    background: #10283A;
}}
QCheckBox {{
    color: {p['text_secondary']};
    spacing: 8px;
    font-size: 11px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid #2A5F7A;
    border-radius: 4px;
    background: #0A1826;
}}
QCheckBox::indicator:hover {{
    border-color: {p['cyan']};
}}
QCheckBox::indicator:checked {{
    background: {p['cyan']};
    border-color: {p['cyan']};
    image: url("{assets['check_dark']}");
}}
QRadioButton {{
    color: {p['text_secondary']};
    spacing: 8px;
    font-size: 11px;
}}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid #2A5F7A;
    border-radius: 7px;
    background: #0A1826;
}}
QRadioButton::indicator:checked {{
    border: 4px solid {p['cyan']};
    background: #04121F;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: #14384A;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {p['cyan']};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {p['text']};
    border: 2px solid {p['cyan']};
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 8px;
}}
QTableView, QTableWidget, QTreeView, QListWidget {{
    background: transparent;
    border: none;
    gridline-color: transparent;
    color: {p['text']};
    font-size: 11px;
    selection-background-color: rgba(0, 217, 245, 0.10);
    selection-color: {p['text']};
    alternate-background-color: #0B1B29;
}}
QTableView::item, QTableWidget::item {{
    border-bottom: 1px solid #102B3D;
    padding: 0px;
}}
QTableView::item:selected, QTableWidget::item:selected {{
    background: rgba(0, 217, 245, 0.10);
    color: {p['text']};
}}
QHeaderView {{
    background: transparent;
}}
QHeaderView::section {{
    background: transparent;
    color: {p['muted']};
    border: none;
    border-bottom: 1px solid {p['border']};
    padding: 6px 8px;
    font-size: 9px;
    font-weight: 600;
}}
QHeaderView::section:hover {{
    color: {p['text_secondary']};
}}
QListWidget::item {{
    padding: 6px 8px;
    border-radius: 6px;
}}
QListWidget::item:hover {{
    background: rgba(0, 217, 245, 0.06);
}}
QListWidget::item:selected {{
    background: rgba(0, 217, 245, 0.12);
    color: {p['text']};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 9px;
    margin: 2px 2px 2px 0;
}}
QScrollBar::handle:vertical {{
    background: #1C4356;
    min-height: 28px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: #2A637C;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 9px;
    margin: 0 2px 2px 2px;
}}
QScrollBar::handle:horizontal {{
    background: #1C4356;
    min-width: 28px;
    border-radius: 4px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
    background: transparent;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
QProgressBar {{
    background: #10283A;
    border: none;
    border-radius: 2px;
    max-height: 4px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p['blue']}, stop:1 {p['cyan']});
    border-radius: 2px;
}}
QToolTip {{
    background: #0C1E2E;
    color: {p['text']};
    border: 1px solid #1E6A82;
    padding: 6px 8px;
    font-size: 11px;
}}
QMenu {{
    background: #0C1E2E;
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 6px 22px 6px 12px;
    border-radius: 5px;
    color: {p['text_secondary']};
}}
QMenu::item:selected {{
    background: rgba(0, 217, 245, 0.12);
    color: {p['text']};
}}
QMenu::separator {{
    height: 1px;
    background: {p['border']};
    margin: 4px 8px;
}}
QDialog {{
    background: {p['bg']};
}}
QGroupBox {{
    border: 1px solid {p['border']};
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 8px;
    color: {p['text_secondary']};
    font-size: 11px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {p['muted']};
}}
QSplitter::handle {{
    background: transparent;
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 3px;
}}
QToolButton:hover {{
    background: rgba(0, 217, 245, 0.09);
    border-color: #1E6A82;
}}
QTabWidget::pane {{
    border: 1px solid {p['border']};
    border-radius: 8px;
}}
QTabBar::tab {{
    background: transparent;
    color: {p['muted']};
    padding: 6px 14px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {p['cyan']};
    border-bottom: 2px solid {p['cyan']};
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    base = QFont(font_family())
    base.setPixelSize(12)
    app.setFont(base)
    app.setStyleSheet(stylesheet())


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
