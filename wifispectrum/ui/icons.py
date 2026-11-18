"""Vector icon set painted with QPainter.

Icons are outline style, 24x24 design grid, stroke based, and tinted at request
time so they always match the active palette. Results are cached per
(name, colour, size, devicePixelRatio).
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)

from ..core.constants import PALETTE

_CACHE: dict[tuple, QIcon] = {}
_CACHE_PIXMAP: dict[tuple, QPixmap] = {}


def _pen(painter: QPainter, color: str, width: float = 1.7):
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)


def _rounded(painter: QPainter, x, y, w, h, r=2.0):
    painter.drawRoundedRect(QRectF(x, y, w, h), r, r)


def _draw(name: str, painter: QPainter, color: str) -> None:
    _pen(painter, color)
    if name == "dashboard":
        for x, y, w, h in ((3.2, 3.2, 7.2, 7.2), (13.6, 3.2, 7.2, 4.6), (3.2, 13.6, 7.2, 7.2), (13.6, 10.6, 7.2, 10.2)):
            _rounded(painter, x, y, w, h, 1.8)
    elif name == "spectrum":
        path = QPainterPath(QPointF(2.5, 13.0))
        for i in range(0, 61):
            x = 2.5 + i * 0.3167
            y = 12.0 - 7.4 * math.sin(i / 60.0 * math.pi * 2.0) * math.sin(i / 60.0 * math.pi)
            path.lineTo(x, y)
        painter.drawPath(path)
        painter.drawLine(QPointF(2.5, 20.5), QPointF(21.5, 20.5))
    elif name == "analyzer":
        for x, top in ((3.5, 15.0), (8.4, 9.0), (13.3, 12.0), (18.2, 5.5)):
            painter.drawLine(QPointF(x, 20.0), QPointF(x, top))
        painter.drawLine(QPointF(2.5, 20.0), QPointF(21.5, 20.0))
    elif name == "discovery":
        painter.drawEllipse(QPointF(12, 12), 8.6, 8.6)
        painter.drawEllipse(QPointF(12, 12), 4.6, 4.6)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(12, 12), 1.35, 1.35)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(12, 12), QPointF(18.4, 5.6))
    elif name == "signal":
        path = QPainterPath(QPointF(3, 16.5))
        for x, y in ((6.2, 12.4), (9.4, 14.2), (12.6, 8.6), (15.8, 10.4), (19.0, 4.8)):
            path.lineTo(x, y)
        painter.drawPath(path)
        for x, y in ((3, 16.5), (6.2, 12.4), (9.4, 14.2), (12.6, 8.6), (15.8, 10.4), (19.0, 4.8)):
            painter.drawEllipse(QPointF(x, y), 1.15, 1.15)
    elif name == "frequency":
        painter.drawLine(QPointF(2.8, 8.6), QPointF(21.2, 8.6))
        painter.drawLine(QPointF(2.8, 18.4), QPointF(21.2, 18.4))
        for x, top in ((5.0, 4.4), (9.4, 6.2), (13.8, 4.4), (18.2, 6.2)):
            painter.drawLine(QPointF(x, top), QPointF(x, 8.6))
        for x, bottom in ((5.0, 22.0), (9.4, 20.4), (13.8, 22.0), (18.2, 20.4)):
            painter.drawLine(QPointF(x, 18.4), QPointF(x, bottom))
    elif name == "history":
        painter.drawEllipse(QPointF(12, 12), 8.5, 8.5)
        painter.drawLine(QPointF(12, 7.0), QPointF(12, 12.3))
        painter.drawLine(QPointF(12, 12.3), QPointF(15.9, 14.4))
    elif name == "hardware":
        _rounded(painter, 5.6, 5.6, 12.8, 12.8, 2.2)
        _rounded(painter, 9.2, 9.2, 5.6, 5.6, 1.2)
        for offset in (7.8, 12.0, 16.2):
            painter.drawLine(QPointF(offset, 2.6), QPointF(offset, 5.6))
            painter.drawLine(QPointF(offset, 18.4), QPointF(offset, 21.4))
            painter.drawLine(QPointF(2.6, offset), QPointF(5.6, offset))
            painter.drawLine(QPointF(18.4, offset), QPointF(21.4, offset))
    elif name == "settings":
        painter.drawEllipse(QPointF(12, 12), 3.4, 3.4)
        for i in range(8):
            angle = i * math.pi / 4.0
            inner = QPointF(12 + 6.2 * math.cos(angle), 12 + 6.2 * math.sin(angle))
            outer = QPointF(12 + 9.1 * math.cos(angle), 12 + 9.1 * math.sin(angle))
            painter.drawLine(inner, outer)
        painter.drawEllipse(QPointF(12, 12), 8.3, 8.3)
    elif name == "wifi":
        for radius in (4.2, 8.0, 11.8):
            rect = QRectF(12 - radius, 12 - radius, radius * 2, radius * 2)
            painter.drawArc(rect, 42 * 16, 96 * 16)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(12, 18.6), 1.5, 1.5)
        painter.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "search":
        painter.drawEllipse(QPointF(10.6, 10.6), 6.4, 6.4)
        painter.drawLine(QPointF(15.4, 15.4), QPointF(20.4, 20.4))
    elif name == "play":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([QPointF(7.8, 4.9), QPointF(19.0, 12.0), QPointF(7.8, 19.1)]))
    elif name == "pause":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        _rounded(painter, 7.0, 5.2, 3.6, 13.6, 1.1)
        _rounded(painter, 13.4, 5.2, 3.6, 13.6, 1.1)
    elif name == "stop":
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        _rounded(painter, 6.4, 6.4, 11.2, 11.2, 2.0)
    elif name == "record":
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(12, 12), 4.2, 4.2)
    elif name == "refresh":
        rect = QRectF(4.4, 4.4, 15.2, 15.2)
        painter.drawArc(rect, 50 * 16, 250 * 16)
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([QPointF(15.2, 2.4), QPointF(20.2, 6.4), QPointF(14.6, 8.4)]))
    elif name == "download":
        painter.drawLine(QPointF(12, 3.6), QPointF(12, 14.4))
        painter.drawPolyline(QPolygonF([QPointF(7.4, 10.2), QPointF(12, 14.8), QPointF(16.6, 10.2)]))
        painter.drawPolyline(QPolygonF([QPointF(4.2, 15.6), QPointF(4.2, 20.4), QPointF(19.8, 20.4), QPointF(19.8, 15.6)]))
    elif name == "upload":
        painter.drawLine(QPointF(12, 20.4), QPointF(12, 8.6))
        painter.drawPolyline(QPolygonF([QPointF(7.4, 13.0), QPointF(12, 8.2), QPointF(16.6, 13.0)]))
        painter.drawPolyline(QPolygonF([QPointF(4.2, 15.6), QPointF(4.2, 20.4), QPointF(19.8, 20.4), QPointF(19.8, 15.6)]))
    elif name == "chevron-down":
        painter.drawPolyline(QPolygonF([QPointF(6.4, 9.4), QPointF(12, 15.0), QPointF(17.6, 9.4)]))
    elif name == "chevron-up":
        painter.drawPolyline(QPolygonF([QPointF(6.4, 14.6), QPointF(12, 9.0), QPointF(17.6, 14.6)]))
    elif name == "chevron-right":
        painter.drawPolyline(QPolygonF([QPointF(9.4, 6.0), QPointF(15.4, 12.0), QPointF(9.4, 18.0)]))
    elif name == "chevron-left":
        painter.drawPolyline(QPolygonF([QPointF(14.6, 6.0), QPointF(8.6, 12.0), QPointF(14.6, 18.0)]))
    elif name == "close":
        painter.drawLine(QPointF(6.4, 6.4), QPointF(17.6, 17.6))
        painter.drawLine(QPointF(17.6, 6.4), QPointF(6.4, 17.6))
    elif name == "check":
        painter.drawPolyline(QPolygonF([QPointF(4.8, 12.6), QPointF(9.8, 17.4), QPointF(19.2, 6.6)]))
    elif name == "plus":
        painter.drawLine(QPointF(12, 5.4), QPointF(12, 18.6))
        painter.drawLine(QPointF(5.4, 12), QPointF(18.6, 12))
    elif name == "minus":
        painter.drawLine(QPointF(5.4, 12), QPointF(18.6, 12))
    elif name == "alert":
        painter.drawPolyline(QPolygonF([QPointF(12, 3.6), QPointF(21.4, 20.2), QPointF(2.6, 20.2), QPointF(12, 3.6)]))
        painter.drawLine(QPointF(12, 9.4), QPointF(12, 14.4))
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(12, 17.2), 0.95, 0.95)
    elif name == "info":
        painter.drawEllipse(QPointF(12, 12), 8.6, 8.6)
        painter.drawLine(QPointF(12, 11.0), QPointF(12, 16.4))
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(12, 7.8), 1.0, 1.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "zap":
        painter.drawPolygon(QPolygonF([QPointF(13.4, 2.8), QPointF(5.6, 13.6), QPointF(11.2, 13.6), QPointF(10.2, 21.2), QPointF(18.4, 10.2), QPointF(12.8, 10.2), QPointF(13.4, 2.8)]))
    elif name == "lock":
        _rounded(painter, 5.0, 10.6, 14.0, 9.8, 2.0)
        painter.drawArc(QRectF(7.8, 3.6, 8.4, 9.6), 0, 180 * 16)
        painter.drawLine(QPointF(7.8, 8.4), QPointF(7.8, 10.6))
        painter.drawLine(QPointF(16.2, 8.4), QPointF(16.2, 10.6))
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(12, 15.4), 1.1, 1.1)
    elif name == "globe":
        painter.drawEllipse(QPointF(12, 12), 8.6, 8.6)
        painter.drawEllipse(QPointF(12, 12), 4.0, 8.6)
        painter.drawLine(QPointF(3.6, 12), QPointF(20.4, 12))
        painter.drawArc(QRectF(3.6, 6.0, 16.8, 12.0), 0, 180 * 16)
    elif name == "clock":
        painter.drawEllipse(QPointF(12, 12), 8.4, 8.4)
        painter.drawLine(QPointF(12, 6.8), QPointF(12, 12.2))
        painter.drawLine(QPointF(12, 12.2), QPointF(15.8, 14.2))
    elif name == "calendar":
        _rounded(painter, 3.6, 5.2, 16.8, 15.2, 2.2)
        painter.drawLine(QPointF(3.6, 9.8), QPointF(20.4, 9.8))
        painter.drawLine(QPointF(8.2, 3.0), QPointF(8.2, 6.6))
        painter.drawLine(QPointF(15.8, 3.0), QPointF(15.8, 6.6))
    elif name == "filter":
        painter.drawPolyline(QPolygonF([QPointF(3.6, 5.4), QPointF(20.4, 5.4), QPointF(13.6, 13.2), QPointF(13.6, 20.0), QPointF(10.4, 17.8), QPointF(10.4, 13.2), QPointF(3.6, 5.4)]))
    elif name == "sort":
        painter.drawLine(QPointF(6.2, 5.0), QPointF(6.2, 19.0))
        painter.drawPolyline(QPolygonF([QPointF(3.2, 8.0), QPointF(6.2, 5.0), QPointF(9.2, 8.0)]))
        painter.drawLine(QPointF(12.6, 7.4), QPointF(20.6, 7.4))
        painter.drawLine(QPointF(12.6, 12.0), QPointF(18.6, 12.0))
        painter.drawLine(QPointF(12.6, 16.6), QPointF(16.6, 16.6))
    elif name == "target":
        painter.drawEllipse(QPointF(12, 12), 8.6, 8.6)
        painter.drawEllipse(QPointF(12, 12), 4.6, 4.6)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(12, 12), 1.3, 1.3)
    elif name == "layers":
        painter.drawPolygon(QPolygonF([QPointF(12, 3.4), QPointF(21.0, 8.4), QPointF(12, 13.4), QPointF(3.0, 8.4)]))
        painter.drawPolyline(QPolygonF([QPointF(3.0, 12.8), QPointF(12, 17.8), QPointF(21.0, 12.8)]))
        painter.drawPolyline(QPolygonF([QPointF(3.0, 16.6), QPointF(12, 21.4), QPointF(21.0, 16.6)]))
    elif name == "palette":
        painter.drawEllipse(QPointF(12, 12), 8.6, 8.6)
        painter.setBrush(QColor(color))
        for x, y in ((9.0, 8.6), (14.8, 9.0), (8.4, 13.6), (13.2, 14.6)):
            painter.drawEllipse(QPointF(x, y), 1.2, 1.2)
        painter.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "eye":
        path = QPainterPath(QPointF(2.6, 12))
        path.cubicTo(7.0, 5.6, 17.0, 5.6, 21.4, 12)
        path.cubicTo(17.0, 18.4, 7.0, 18.4, 2.6, 12)
        painter.drawPath(path)
        painter.drawEllipse(QPointF(12, 12), 3.1, 3.1)
    elif name == "trash":
        painter.drawLine(QPointF(4.0, 6.6), QPointF(20.0, 6.6))
        painter.drawPolyline(QPolygonF([QPointF(9.0, 6.6), QPointF(9.6, 3.8), QPointF(14.4, 3.8), QPointF(15.0, 6.6)]))
        painter.drawPolyline(QPolygonF([QPointF(6.4, 6.6), QPointF(7.4, 20.2), QPointF(16.6, 20.2), QPointF(17.6, 6.6)]))
        painter.drawLine(QPointF(10.2, 10.0), QPointF(10.6, 17.0))
        painter.drawLine(QPointF(13.8, 10.0), QPointF(13.4, 17.0))
    elif name == "maximize":
        for x1, y1, x2, y2 in ((4.0, 9.4, 4.0, 4.0), (4.0, 4.0, 9.4, 4.0),
                               (14.6, 4.0, 20.0, 4.0), (20.0, 4.0, 20.0, 9.4),
                               (20.0, 14.6, 20.0, 20.0), (20.0, 20.0, 14.6, 20.0),
                               (9.4, 20.0, 4.0, 20.0), (4.0, 20.0, 4.0, 14.6)):
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    elif name == "doc":
        painter.drawPolyline(QPolygonF([QPointF(5.6, 3.2), QPointF(14.0, 3.2), QPointF(18.6, 7.8), QPointF(18.6, 20.8), QPointF(5.6, 20.8), QPointF(5.6, 3.2)]))
        painter.drawPolyline(QPolygonF([QPointF(13.8, 3.4), QPointF(13.8, 8.0), QPointF(18.4, 8.0)]))
        painter.drawLine(QPointF(8.4, 12.4), QPointF(15.8, 12.4))
        painter.drawLine(QPointF(8.4, 16.2), QPointF(13.6, 16.2))
    elif name == "grid":
        for x in (4.0, 12.0, 20.0):
            painter.drawLine(QPointF(x, 4.0), QPointF(x, 20.0))
        for y in (4.0, 12.0, 20.0):
            painter.drawLine(QPointF(4.0, y), QPointF(20.0, y))
    elif name == "arrow-up":
        painter.drawLine(QPointF(12, 20.0), QPointF(12, 5.0))
        painter.drawPolyline(QPolygonF([QPointF(6.4, 10.4), QPointF(12, 4.6), QPointF(17.6, 10.4)]))
    elif name == "arrow-down":
        painter.drawLine(QPointF(12, 4.0), QPointF(12, 19.0))
        painter.drawPolyline(QPolygonF([QPointF(6.4, 13.6), QPointF(12, 19.4), QPointF(17.6, 13.6)]))
    elif name == "antenna":
        painter.drawLine(QPointF(12, 21.0), QPointF(12, 9.0))
        painter.drawEllipse(QPointF(12, 7.2), 2.2, 2.2)
        painter.drawArc(QRectF(6.4, 1.6, 11.2, 11.2), 20 * 16, 140 * 16)
        painter.drawLine(QPointF(6.0, 21.0), QPointF(18.0, 21.0))
    else:
        _rounded(painter, 4.5, 4.5, 15.0, 15.0, 3.0)


def pixmap(name: str, color: str = PALETTE["cyan"], size: int = 22, dpr: float = 1.0) -> QPixmap:
    key = (name, color, size, round(dpr, 2))
    if key in _CACHE_PIXMAP:
        return _CACHE_PIXMAP[key]
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.scale(size / 24.0, size / 24.0)
    _draw(name, painter, color)
    painter.end()
    _CACHE_PIXMAP[key] = px
    return px


def icon(name: str, color: str = PALETTE["cyan"], size: int = 22) -> QIcon:
    key = (name, color, size)
    if key in _CACHE:
        return _CACHE[key]
    result = QIcon()
    for scale in (1.0, 2.0):
        result.addPixmap(pixmap(name, color, size, scale))
    _CACHE[key] = result
    return result


def app_icon() -> QIcon:
    """Multi-resolution application icon (window, launcher, task bar)."""
    result = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        px = QPixmap(size, size)
        px.fill(Qt.GlobalColor.transparent)
        painter = QPainter(px)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.scale(size / 64.0, size / 64.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#08131F"))
        painter.drawRoundedRect(QRectF(1, 1, 62, 62), 13, 13)
        pen = QPen(QColor("#00D9F5"))
        pen.setWidthF(3.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for radius, start in ((9.0, 42), (16.5, 42), (24.0, 42)):
            rect = QRectF(32 - radius, 32 - radius + 6, radius * 2, radius * 2)
            painter.drawArc(rect, start * 16, 96 * 16)
        painter.setBrush(QColor("#00E89A"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(32, 45), 3.4, 3.4)
        painter.end()
        result.addPixmap(px)
    return result
