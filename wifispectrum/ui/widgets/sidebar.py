"""Left navigation sidebar."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ...core.constants import APP_NAME, APP_SUBTITLE, APP_TAGLINE, APP_VERSION, NAV_ITEMS, PALETTE
from .. import icons
from ..theme import font
from .base import label, tint


class LogoMark(QWidget):
    def __init__(self, size: int = 40, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._size = size

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, 11, 11)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor("#0E3B50"))
        grad.setColorAt(1.0, QColor("#0A2130"))
        painter.fillPath(path, grad)
        pen = QPen(tint(PALETTE["cyan"], 0.55))
        pen.setWidthF(1.1)
        painter.setPen(pen)
        painter.drawPath(path)
        glow = QRadialGradient(QPointF(self.width() / 2, self.height() / 2), self.width() * 0.62)
        glow.setColorAt(0.0, tint(PALETTE["cyan"], 0.18))
        glow.setColorAt(1.0, tint(PALETTE["cyan"], 0.0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawPath(path)
        pixmap = icons.pixmap("wifi", PALETTE["cyan"], int(self.width() * 0.62), self.devicePixelRatioF())
        painter.drawPixmap(
            int((self.width() - pixmap.width() / pixmap.devicePixelRatio()) / 2),
            int((self.height() - pixmap.height() / pixmap.devicePixelRatio()) / 2),
            pixmap,
        )
        painter.end()


class NavButton(QWidget):
    clicked = Signal(str)

    def __init__(self, key: str, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.key = key
        self._text = text
        self._selected = False
        self._hover = False
        self._badge = ""
        self._icon = icons.pixmap(key, PALETTE["text_secondary"], 18)
        self._icon_active = icons.pixmap(key, PALETTE["cyan"], 18)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_selected(self, selected: bool) -> None:
        if selected != self._selected:
            self._selected = selected
            self.update()

    def set_badge(self, text: str) -> None:
        self._badge = text
        self.update()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)

        if self._selected:
            for grow in (2.0, 1.0):
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(tint(PALETTE["cyan"], 0.045))
                painter.drawRoundedRect(rect.adjusted(-grow, -grow * 0.4, grow, grow * 0.4), 9, 9)
            grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
            grad.setColorAt(0.0, tint(PALETTE["cyan"], 0.20))
            grad.setColorAt(0.65, tint(PALETTE["cyan"], 0.07))
            grad.setColorAt(1.0, tint(PALETTE["cyan"], 0.02))
            painter.setBrush(grad)
            painter.setPen(QPen(tint(PALETTE["cyan"], 0.80), 1.0))
            painter.drawRoundedRect(rect, 9, 9)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(PALETTE["cyan"]))
            painter.drawRoundedRect(QRectF(0.5, 9, 2.4, self.height() - 18), 1.2, 1.2)
        elif self._hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tint(PALETTE["text"], 0.045))
            painter.drawRoundedRect(rect, 9, 9)

        pixmap = self._icon_active if self._selected else self._icon
        painter.drawPixmap(14, int((self.height() - 18) / 2), pixmap)

        painter.setFont(font(11.5, 600 if self._selected else 500, 0.15))
        painter.setPen(
            QColor(PALETTE["text"] if self._selected else (PALETTE["text_secondary"] if self._hover else PALETTE["text_secondary"]))
        )
        painter.drawText(
            QRectF(43, 0, self.width() - 76, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._text,
        )

        if self._badge:
            painter.setFont(font(8, 600, 0.4))
            fm = painter.fontMetrics()
            width = fm.horizontalAdvance(self._badge) + 12
            badge_rect = QRectF(self.width() - width - 12, (self.height() - 17) / 2, width, 17)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tint(PALETTE["cyan"], 0.14))
            painter.drawRoundedRect(badge_rect, 8, 8)
            painter.setPen(QColor(PALETTE["cyan"]))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, self._badge)
        painter.end()


class Sidebar(QWidget):
    navigate = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(240)
        self._buttons: dict[str, NavButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 14)
        layout.setSpacing(0)

        # brand
        brand = QHBoxLayout()
        brand.setContentsMargins(4, 0, 0, 0)
        brand.setSpacing(10)
        brand.addWidget(LogoMark(40))
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)
        name = QLabel("WiFi Spectrum")
        name.setFont(font(13.5, 600, 0.1))
        name.setStyleSheet(f"color: {PALETTE['text']};")
        studio = QLabel("STUDIO")
        studio.setFont(font(8, 600, 2.4))
        studio.setStyleSheet(f"color: {PALETTE['cyan']};")
        text_col.addWidget(name)
        text_col.addWidget(studio)
        brand.addLayout(text_col, 1)
        layout.addLayout(brand)

        subtitle = label(APP_SUBTITLE, 8.5, PALETTE["muted"], 400, 0.4)
        subtitle.setContentsMargins(5, 7, 0, 0)
        layout.addWidget(subtitle)

        layout.addSpacing(18)
        section = label("NAVIGATION", 7.5, PALETTE["muted"], 600, 1.6)
        section.setContentsMargins(8, 0, 0, 6)
        layout.addWidget(section)
        layout.addSpacing(2)

        for key, text in NAV_ITEMS:
            button = NavButton(key, text)
            button.clicked.connect(self.navigate.emit)
            self._buttons[key] = button
            layout.addWidget(button)
            layout.addSpacing(3)

        layout.addStretch(1)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #123246; border: none;")
        layout.addWidget(divider)
        layout.addSpacing(14)

        footer = QHBoxLayout()
        footer.setContentsMargins(6, 0, 0, 0)
        footer.setSpacing(10)
        mark = QLabel()
        mark.setPixmap(icons.pixmap("wifi", PALETTE["cyan"], 30, self.devicePixelRatioF()))
        footer.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
        foot_text = QVBoxLayout()
        foot_text.setContentsMargins(0, 0, 0, 0)
        foot_text.setSpacing(2)
        foot_name = label(APP_NAME, 9.5, PALETTE["text_secondary"], 600, 0.1)
        foot_name.setWordWrap(True)
        foot_desc = label(APP_TAGLINE, 8, PALETTE["muted"], 400, 0.2, wrap=True)
        foot_text.addWidget(foot_name)
        foot_text.addWidget(foot_desc)
        foot_text.addSpacing(4)
        version = label(f"v{APP_VERSION}", 7.5, PALETTE["muted"], 400, 0.5)
        foot_text.addWidget(version)
        footer.addLayout(foot_text, 1)
        layout.addLayout(footer)

    # -- API ---------------------------------------------------------------
    def set_selected(self, key: str) -> None:
        for item_key, button in self._buttons.items():
            button.set_selected(item_key == key)

    def set_badge(self, key: str, text: str) -> None:
        button = self._buttons.get(key)
        if button:
            button.set_badge(text)

    def sizeHint(self) -> QSize:
        return QSize(240, 800)
