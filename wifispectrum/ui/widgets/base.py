"""Reusable UI primitives: panels, cards, pills, segmented control, empty states."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import PALETTE
from .. import icons
from ..theme import font, mono_family


def rgba(color: str, alpha: float) -> str:
    color = color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def tint(color: str, alpha: float) -> QColor:
    """Build a QColor with an explicit alpha.

    Qt's QColor parser rejects the CSS ``rgba(...)`` strings that style sheets
    accept, so all painting code must go through this helper instead.
    """
    value = QColor(color)
    value.setAlphaF(max(0.0, min(1.0, alpha)))
    return value


def label(
    text: str = "",
    size: int = 12,
    color: str | None = None,
    weight: int = 400,
    spacing: float = 0.0,
    upper: bool = False,
    wrap: bool = False,
) -> QLabel:
    widget = QLabel(text.upper() if upper else text)
    widget.setFont(font(size, weight, spacing))
    if color:
        widget.setStyleSheet(f"color: {color}; background: transparent;")
    widget.setWordWrap(wrap)
    return widget


def vline(height: int = 18) -> QFrame:
    frame = QFrame()
    frame.setFixedSize(1, height)
    frame.setStyleSheet("background: #17465B; border: none;")
    return frame


def hline() -> QFrame:
    frame = QFrame()
    frame.setObjectName("Divider")
    frame.setFixedHeight(1)
    frame.setStyleSheet("background: #123246; border: none;")
    return frame


class Panel(QFrame):
    """Rounded analysis panel with a header row and an actions area."""

    def __init__(self, title: str = "", hint: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setFrameShape(QFrame.Shape.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 11, 14, 12)
        outer.setSpacing(8)

        self.header = QHBoxLayout()
        self.header.setContentsMargins(0, 0, 0, 0)
        self.header.setSpacing(8)

        self.title_label = label(title, 11, PALETTE["text"], 600, 1.25, upper=True)
        self.hint_label = label(hint, 10, PALETTE["muted"], 400, 0.2)
        self.header.addWidget(self.title_label)
        self.header.addWidget(self.hint_label)
        self.header.addStretch(1)

        self.actions = QHBoxLayout()
        self.actions.setContentsMargins(0, 0, 0, 0)
        self.actions.setSpacing(4)
        self.header.addLayout(self.actions)
        outer.addLayout(self.header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        outer.addLayout(self.body, 1)
        self._outer = outer

    def add_action(self, widget: QWidget) -> None:
        self.actions.addWidget(widget)

    def set_title(self, text: str) -> None:
        self.title_label.setText(text.upper())

    def set_hint(self, text: str) -> None:
        self.hint_label.setText(text)

    def add(self, widget: QWidget, stretch: int = 0) -> None:
        self.body.addWidget(widget, stretch)

    def add_layout(self, layout, stretch: int = 0) -> None:
        self.body.addLayout(layout, stretch)

    def set_margins(self, left: int, top: int, right: int, bottom: int) -> None:
        self._outer.setContentsMargins(left, top, right, bottom)


class IconTile(QWidget):
    """Rounded, tinted icon tile used by metric cards and lists."""

    def __init__(self, icon_name: str, color: str, size: int = 38, icon_size: int = 20,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._color = color
        self._icon_size = icon_size
        self.setFixedSize(size, size)

    def set_icon(self, name: str, color: str | None = None) -> None:
        self._icon_name = name
        if color:
            self._color = color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, tint(self._color, 0.20))
        grad.setColorAt(1.0, tint(self._color, 0.05))
        painter.fillPath(path, grad)
        pen = QPen(tint(self._color, 0.42))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawPath(path)
        pixmap = icons.pixmap(self._icon_name, self._color, self._icon_size, self.devicePixelRatioF())
        painter.drawPixmap(
            int((self.width() - self._icon_size) / 2),
            int((self.height() - self._icon_size) / 2),
            pixmap,
        )
        painter.end()


class MetricCard(QFrame):
    """Compact KPI card with an icon tile, large value and caption."""

    def __init__(self, title: str, icon_name: str, accent: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setMinimumHeight(82)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._accent = accent
        self._icon_name = icon_name
        self._title = title

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 11)
        layout.setSpacing(11)

        self.icon_box = IconTile(icon_name, accent, 38, 20)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        self.value_label = label("--", 22, PALETTE["text"], 600, 0.2)
        self.title_label = label(title, 9, PALETTE["muted"], 500, 0.9, upper=True)
        self.sub_label = label("", 9, PALETTE["text_secondary"], 400, 0.1)
        text_col.addWidget(self.value_label)
        text_col.addWidget(self.title_label)
        text_col.addWidget(self.sub_label)

        layout.addWidget(self.icon_box, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_col, 1)


    def set_value(self, value: str, sub: str | None = None, color: str | None = None) -> None:
        self.value_label.setText(value)
        self.value_label.setStyleSheet(f"color: {color or PALETTE['text']}; background: transparent;")
        if sub is not None:
            self.sub_label.setText(sub)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(1.0, self.height() - 2.2, self.width() - 2.0, 2.2)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 12, 12)
        painter.setClipPath(clip)
        grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
        grad.setColorAt(0.0, tint(self._accent, 0.0))
        grad.setColorAt(0.12, tint(self._accent, 0.85))
        grad.setColorAt(0.55, tint(self._accent, 0.28))
        grad.setColorAt(1.0, tint(self._accent, 0.0))
        painter.fillRect(rect, grad)
        painter.end()


class PulseDot(QWidget):
    """Small live indicator with a slow, subtle glow pulse."""

    def __init__(self, color: str = PALETTE["green"], size: int = 10, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._advance)
        self._timer.start()
        self.setFixedSize(size + 8, size + 8)
        self._size = size

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def _advance(self) -> None:
        self._phase = (self._phase + 0.035) % 1.0
        if self.isVisible():
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        import math

        glow = 0.30 + 0.22 * (0.5 + 0.5 * math.sin(self._phase * math.tau))
        center = QPointF(self.width() / 2, self.height() / 2)
        radial = QRadialGradient(center, self._size)
        radial.setColorAt(0.0, tint(self._color, glow))
        radial.setColorAt(1.0, tint(self._color, 0.0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(radial)
        painter.drawEllipse(center, self._size, self._size)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(center, self._size / 2.4, self._size / 2.4)
        painter.end()


class Pill(QWidget):
    """Rounded status pill with a colour dot and text."""

    def __init__(self, text: str, color: str = PALETTE["cyan"], parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self._text = text
        self._dot = True
        self.setFont(font(9, 600, 0.9))

    def set_text(self, text: str) -> None:
        self._text = text
        self.updateGeometry()
        self.update()

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def set_dot(self, visible: bool) -> None:
        self._dot = visible
        self.update()

    def sizeHint(self) -> QSize:
        width = self.fontMetrics().horizontalAdvance(self._text.upper()) + 22 + (10 if self._dot else 0)
        return QSize(width, 22)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setBrush(tint(self._color, 0.10))
        pen = QPen(tint(self._color, 0.38))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        x = 11.0
        if self._dot:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self._color))
            painter.drawEllipse(QPointF(x, self.height() / 2), 2.4, 2.4)
            x += 9.0
        painter.setPen(QColor(self._color))
        painter.setFont(self.font())
        painter.drawText(
            QRectF(x, 0, self.width() - x - 8, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._text.upper(),
        )
        painter.end()


class SegmentedControl(QWidget):
    """Pill-style selector used for bands and view modes."""

    changed = Signal(str)

    def __init__(self, items: list[tuple[str, str]], parent: QWidget | None = None):
        super().__init__(parent)
        self._items = items  # (key, label)
        self._current = items[0][0] if items else ""
        self._disabled: set[str] = set()
        self._hover = -1
        self.setMouseTracking(True)
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(self._preferred_width())

    def _preferred_width(self) -> int:
        width = 12
        for _, text in self._items:
            width += max(58, self.fontMetrics().horizontalAdvance(text) + 30)
        return width

    def set_items(self, items: list[tuple[str, str]]) -> None:
        self._items = items
        if self._current not in [key for key, _ in items]:
            self._current = items[0][0] if items else ""
        self.setMinimumWidth(self._preferred_width())
        self.update()

    @property
    def current(self) -> str:
        return self._current

    def set_current(self, key: str, emit: bool = False) -> None:
        if key == self._current:
            return
        self._current = key
        self.update()
        if emit:
            self.changed.emit(key)

    def set_disabled(self, keys: set[str]) -> None:
        self._disabled = set(keys)
        self.update()

    def _segment_rects(self) -> list[QRectF]:
        count = max(1, len(self._items))
        width = self.width() - 6
        seg = width / count
        return [QRectF(3 + i * seg, 3, seg, self.height() - 6) for i in range(count)]

    def _index_at(self, x: float) -> int:
        for index, rect in enumerate(self._segment_rects()):
            if rect.contains(QPointF(x, self.height() / 2)):
                return index
        return -1

    def mouseMoveEvent(self, event) -> None:
        index = self._index_at(event.position().x())
        if index != self._hover:
            self._hover = index
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        index = self._index_at(event.position().x())
        if 0 <= index < len(self._items):
            key = self._items[index][0]
            if key not in self._disabled:
                self.set_current(key, emit=True)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setBrush(QColor("#0A1826"))
        pen = QPen(QColor("#123246"))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawRoundedRect(outer, 9, 9)

        for index, ((key, text), rect) in enumerate(zip(self._items, self._segment_rects())):
            selected = key == self._current
            disabled = key in self._disabled
            if selected:
                for grow in (3, 2, 1):
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(tint(PALETTE["cyan"], 0.05 * grow))
                    painter.drawRoundedRect(rect.adjusted(-grow * 0.4, -grow * 0.4, grow * 0.4, grow * 0.4), 8, 8)
                painter.setBrush(tint(PALETTE["cyan"], 0.16))
                pen = QPen(QColor(PALETTE["cyan"]))
                pen.setWidthF(1.0)
                painter.setPen(pen)
                painter.drawRoundedRect(rect, 7, 7)
            elif index == self._hover and not disabled:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(tint(PALETTE["text"], 0.05))
                painter.drawRoundedRect(rect, 7, 7)

            if disabled:
                color = QColor("#40596B")
            elif selected:
                color = QColor(PALETTE["text"])
            else:
                color = QColor(PALETTE["text_secondary"])
            painter.setPen(color)
            painter.setFont(font(11, 600 if selected else 500, 0.6))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.end()


class IconButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str = "", size: int = 26, icon_size: int = 15,
                 color: str = PALETTE["text_secondary"], parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("IconButton")
        self.setFixedSize(size, size)
        self.setIcon(icons.icon(icon_name, color, icon_size))
        self.setIconSize(QSize(icon_size, icon_size))
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_name = icon_name
        self._icon_color = color
        self._icon_size = icon_size

    def set_icon_name(self, name: str, color: str | None = None) -> None:
        self._icon_name = name
        if color:
            self._icon_color = color
        self.setIcon(icons.icon(self._icon_name, self._icon_color, self._icon_size))


class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "Search networks...", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Search")
        self.setPlaceholderText(placeholder)
        self.addAction(icons.icon("search", PALETTE["muted"], 15), QLineEdit.ActionPosition.LeadingPosition)
        self.setClearButtonEnabled(True)
        self.setFixedHeight(30)


class EmptyState(QWidget):
    """Clear, honest empty state used whenever real data is unavailable."""

    def __init__(self, icon_name: str, title: str, detail: str, action_text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        layout.setSpacing(6)
        layout.addStretch(1)

        icon_label = QLabel()
        icon_label.setPixmap(icons.pixmap(icon_name, PALETTE["muted"], 30, self.devicePixelRatioF()))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        self.title = label(title, 12, PALETTE["text_secondary"], 600)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        self.detail = label(detail, 10, PALETTE["muted"], 400, 0.1, wrap=True)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.detail)

        self.button = None
        if action_text:
            self.button = QPushButton(action_text)
            self.button.setObjectName("Ghost")
            self.button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.button.setFixedHeight(26)
            self.button.setStyleSheet("padding: 2px 12px; font-size: 10px;")
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(self.button)
            row.addStretch(1)
            layout.addSpacing(2)
            layout.addLayout(row)
        layout.addStretch(1)


class Badge(QLabel):
    def __init__(self, text: str, color: str = PALETTE["cyan"], parent: QWidget | None = None):
        super().__init__(text.upper(), parent)
        self.setFont(font(9, 600, 0.9))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"color: {color}; background: {rgba(color, 0.10)}; border: 1px solid {rgba(color, 0.36)};"
            f" border-radius: 7px; padding: 1px 7px;"
        )


class KeyValueRow(QWidget):
    def __init__(self, key: str, value: str = "", value_color: str | None = None,
                 parent: QWidget | None = None, fixed_key: int | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.key = label(key, 10, PALETTE["muted"], 400, 0.3)
        self.value = label(value, 10.5, value_color or PALETTE["text"], 500, 0.1)
        if fixed_key:
            self.key.setFixedWidth(fixed_key)
            layout.addWidget(self.key)
            self.value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(self.value, 1)
        else:
            self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(self.key)
            layout.addStretch(1)
            layout.addWidget(self.value)

    def set_value(self, text: str, color: str | None = None) -> None:
        self.value.setText(text)
        if color:
            self.value.setStyleSheet(f"color: {color}; background: transparent;")


class StatBlock(QWidget):
    """Small stacked value/caption used inside detail panels."""

    def __init__(self, caption: str, value: str = "--", color: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        self.value = label(value, 16, color or PALETTE["text"], 600, 0.2)
        self.caption = label(caption, 9, PALETTE["muted"], 500, 0.7, upper=True)
        layout.addWidget(self.value)
        layout.addWidget(self.caption)

    def set_value(self, text: str, color: str | None = None) -> None:
        self.value.setText(text)
        if color:
            self.value.setStyleSheet(f"color: {color}; background: transparent;")


class MonoLabel(QLabel):
    def __init__(self, text: str = "", size: int = 10, color: str | None = None, parent: QWidget | None = None):
        super().__init__(text, parent)
        f = QFont(mono_family())
        f.setPixelSize(size)
        self.setFont(f)
        if color:
            self.setStyleSheet(f"color: {color}; background: transparent;")


class Sparkline(QWidget):
    """Tiny inline trend line (used on the dashboard)."""

    def __init__(self, color: str = PALETTE["cyan"], parent: QWidget | None = None):
        super().__init__(parent)
        self._values: list[float] = []
        self._color = color
        self.setMinimumHeight(30)

    def set_values(self, values: list[float]) -> None:
        self._values = values[-80:]
        self.update()

    def paintEvent(self, event) -> None:
        if len(self._values) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        lo, hi = min(self._values), max(self._values)
        span = max(1.0, hi - lo)
        w = self.width() - 2
        h = self.height() - 6
        path = QPainterPath()
        for index, value in enumerate(self._values):
            x = 1 + w * index / (len(self._values) - 1)
            y = 3 + h * (1 - (value - lo) / span)
            if index == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        fill = QPainterPath(path)
        fill.lineTo(1 + w, self.height())
        fill.lineTo(1, self.height())
        fill.closeSubpath()
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, tint(self._color, 0.28))
        grad.setColorAt(1, tint(self._color, 0.0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawPath(fill)
        pen = QPen(QColor(self._color))
        pen.setWidthF(1.4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()


class PageHeader(QWidget):
    """Consistent page title block with a right-hand action area."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(10)

        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self.title = label(title, 17, PALETTE["text"], 600, 0.2)
        self.subtitle = label(subtitle, 9.5, PALETTE["muted"], 400, 0.1)
        column.addWidget(self.title)
        column.addWidget(self.subtitle)
        row.addLayout(column)
        row.addStretch(1)

        self.actions = QHBoxLayout()
        self.actions.setContentsMargins(0, 0, 0, 0)
        self.actions.setSpacing(8)
        row.addLayout(self.actions)

    def add_action(self, widget: QWidget) -> None:
        self.actions.addWidget(widget)

    def set_subtitle(self, text: str) -> None:
        self.subtitle.setText(text)


class ToggleSwitch(QAbstractButton):
    """Small painted on/off switch used by the settings page."""

    def __init__(self, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(40, 22)
        self.toggled.connect(lambda _: self.update())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        track = QRectF(0.5, 1.5, self.width() - 1, self.height() - 3)
        on = self.isChecked()
        painter.setPen(QPen(tint(PALETTE["cyan"] if on else PALETTE["border"], 0.7), 1))
        painter.setBrush(tint(PALETTE["cyan"], 0.20) if on else QColor("#0A1A28"))
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)

        radius = track.height() / 2 - 2.5
        center_y = track.center().y()
        center_x = track.right() - radius - 3 if on else track.left() + radius + 3
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(PALETTE["cyan"] if on else PALETTE["muted"]))
        painter.drawEllipse(QPointF(center_x, center_y), radius, radius)
        painter.end()


class MeterBar(QWidget):
    """Thin horizontal progress/occupancy bar."""

    def __init__(self, value: float = 0.0, color: str = PALETTE["cyan"], height: int = 6,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._value = max(0.0, min(100.0, float(value)))
        self._color = color
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_value(self, value: float, color: str | None = None) -> None:
        self._value = max(0.0, min(100.0, float(value)))
        if color:
            self._color = color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        track = QRectF(0, 0, self.width(), self.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#0A1B29"))
        painter.drawRoundedRect(track, self.height() / 2, self.height() / 2)
        if self._value <= 0.4:
            painter.end()
            return
        fill = QRectF(0, 0, max(self.height(), self.width() * self._value / 100.0), self.height())
        grad = QLinearGradient(fill.left(), 0, fill.right(), 0)
        grad.setColorAt(0.0, tint(self._color, 0.55))
        grad.setColorAt(1.0, tint(self._color, 0.95))
        painter.setBrush(grad)
        painter.drawRoundedRect(fill, self.height() / 2, self.height() / 2)
        painter.end()
