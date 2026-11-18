"""Hardware: adapters, capabilities, SDR/FFT status and diagnostics."""

from __future__ import annotations

import platform
import sys
import time

from PySide6.QtCore import QThreadPool, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import APP_NAME, APP_VERSION, PALETTE
from ...core.events import bus
from ...core.platform import data_dir, log_dir
from ...core.models import AdapterInfo
from ...workers.tasks import Task
from .. import icons
from ..widgets.base import (
    Badge,
    PageHeader,
    Panel,
    KeyValueRow,
    label,
    rgba,
)
from ..widgets.notice import NoticeBar


class AdapterCard(QWidget):
    clicked = Signal()

    def __init__(self, adapter: AdapterInfo, active: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.adapter = adapter
        self._active = active
        self.setObjectName("AdapterCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(76)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.name = label(adapter.name, 10, PALETTE["text"], 600, 0.05)
        top.addWidget(self.name, 1)
        if adapter.is_demo:
            demo = label("DEMO", 7, PALETTE["yellow"], 700, 0.8)
            demo.setStyleSheet(
                f"color: {PALETTE['yellow']}; background: {rgba(PALETTE['yellow'], 0.12)};"
                f" border: 1px solid {rgba(PALETTE['yellow'], 0.4)}; border-radius: 6px; padding: 0 5px;"
            )
            top.addWidget(demo)
        layout.addLayout(top)

        meta = label(
            f"{adapter.interface}  \u2022  {adapter.backend}  \u2022  {adapter.band_labels}",
            8,
            PALETTE["muted"],
            500,
            0.3,
        )
        layout.addWidget(meta)
        caps = label(
            "monitor mode" if adapter.monitor_capable else "managed mode only",
            7.6,
            PALETTE["text_secondary"] if adapter.monitor_capable else PALETTE["muted"],
            500,
            0.2,
        )
        layout.addWidget(caps)
        self._apply_style()

    def _apply_style(self) -> None:
        # Child labels would inherit an unscoped rule (Qt cascades stylesheets),
        # so target the card itself by object name.
        if self._active:
            self.setStyleSheet(
                f"#AdapterCard {{ background: {rgba(PALETTE['cyan'], 0.07)};"
                f" border: 1px solid {rgba(PALETTE['cyan'], 0.34)}; border-radius: 9px; }}"
            )
        else:
            self.setStyleSheet(
                f"#AdapterCard {{ background: {rgba('#0A1826', 0.7)};"
                f" border: 1px solid {rgba('#17465B', 0.5)}; border-radius: 9px; }}"
            )

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_style()

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)


class AdapterList(QWidget):
    adapter_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._cards: dict[str, AdapterCard] = {}
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 4, 0)
        self._layout.setSpacing(6)
        self._layout.addStretch(1)

    def set_adapters(self, adapters: list[AdapterInfo], selected: AdapterInfo | None) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()
        for adapter in adapters:
            card = AdapterCard(adapter, bool(selected and adapter.interface == selected.interface))
            card.clicked.connect(lambda a=adapter: self._pick(a))
            self._cards[adapter.interface] = card
            self._layout.addWidget(card)
        self._layout.addStretch(1)

    def _pick(self, adapter: AdapterInfo) -> None:
        for key, card in self._cards.items():
            card.set_active(key == adapter.interface)
        self.adapter_selected.emit(adapter.interface)


class HardwarePage(QWidget):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._adapter: AdapterInfo | None = None
        self._task: Task | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(9)

        header = PageHeader(
            "Hardware",
            "Wireless adapters, band capabilities and optional SDR hardware",
        )
        self.refresh_button = QPushButton("  Refresh")
        self.refresh_button.setObjectName("Ghost")
        self.refresh_button.setIcon(icons.icon("refresh", PALETTE["text_secondary"], 14))
        self.refresh_button.setFixedHeight(28)
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.clicked.connect(self._refresh_adapters)
        header.add_action(self.refresh_button)
        root.addWidget(header)

        self.notice = NoticeBar()
        root.addWidget(self.notice)

        body = QHBoxLayout()
        body.setSpacing(9)

        # -- adapter list --------------------------------------------------
        self.list_panel = Panel("Wireless Adapters", "SELECT TO INSPECT")
        self.list_badge = Badge("0", PALETTE["cyan"])
        self.list_panel.add_action(self.list_badge)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("background: transparent;")
        self.adapter_list = AdapterList()
        self.adapter_list.adapter_selected.connect(self._select)
        self.scroll.setWidget(self.adapter_list)
        self.list_panel.add(self.scroll, 1)
        self.list_panel.setFixedWidth(360)
        body.addWidget(self.list_panel)

        # -- adapter details ----------------------------------------------
        self.detail_panel = Panel("Adapter Details", "CAPABILITIES AND DRIVER")
        self.detail_badge = Badge("NO ADAPTER", PALETTE["muted"])
        self.detail_panel.add_action(self.detail_badge)

        columns = QHBoxLayout()
        columns.setSpacing(22)
        left_col = QVBoxLayout()
        left_col.setSpacing(7)
        right_col = QVBoxLayout()
        right_col.setSpacing(7)
        self.detail_rows = {
            "interface": KeyValueRow("Interface", "\u2014", fixed_key=100),
            "name": KeyValueRow("Adapter", "\u2014", fixed_key=100),
            "vendor": KeyValueRow("Vendor", "\u2014", fixed_key=100),
            "chipset": KeyValueRow("Chipset", "\u2014", fixed_key=100),
            "driver": KeyValueRow("Driver", "\u2014", fixed_key=100),
            "version": KeyValueRow("Driver version", "\u2014", fixed_key=100),
            "backend": KeyValueRow("Backend", "\u2014", fixed_key=100),
            "bands": KeyValueRow("Supported bands", "\u2014", fixed_key=100),
            "widths": KeyValueRow("Channel widths", "\u2014", fixed_key=100),
            "monitor": KeyValueRow("Monitor mode", "\u2014", fixed_key=100),
            "fft": KeyValueRow("FFT capable", "\u2014", fixed_key=100),
            "source": KeyValueRow("Data source", "\u2014", fixed_key=100),
        }
        keys = list(self.detail_rows)
        for key in keys[:6]:
            left_col.addWidget(self.detail_rows[key])
        for key in keys[6:]:
            right_col.addWidget(self.detail_rows[key])
        left_col.addStretch(1)
        right_col.addStretch(1)
        columns.addLayout(left_col, 1)
        columns.addLayout(right_col, 1)
        self.detail_panel.add_layout(columns)

        self.detail_notes = label("", 8.2, PALETTE["muted"], 400, 0.15, wrap=True)
        self.detail_panel.add(self.detail_notes)
        self.detail_panel.body.addStretch(1)
        body.addWidget(self.detail_panel, 1)
        root.addLayout(body, 1)

        # -- SDR + diagnostics --------------------------------------------
        bottom = QHBoxLayout()
        bottom.setSpacing(9)

        self.sdr_panel = Panel("SDR / True FFT", "SOAPYSDR PROBE")
        self.sdr_badge = Badge("NOT PROBED", PALETTE["muted"])
        self.sdr_panel.add_action(self.sdr_badge)
        self.sdr_status = label("No SDR detected", 14, PALETTE["muted"], 600, 0.1)
        self.sdr_panel.add(self.sdr_status)
        self.sdr_reason = label(
            "Wi-Fi curves in this application are channel-shaped visualisations built from scan data, "
            "not measured RF. Live FFT traces require a supported SoapySDR device.",
            8.6,
            PALETTE["text_secondary"],
            400,
            0.05,
            wrap=True,
        )
        self.sdr_panel.add(self.sdr_reason)
        self.sdr_devices = label("", 8.4, PALETTE["muted"], 400, 0.3, wrap=True)
        self.sdr_panel.add(self.sdr_devices)
        self.probe_button = QPushButton("  Probe again")
        self.probe_button.setObjectName("Ghost")
        self.probe_button.setFixedHeight(26)
        self.probe_button.setFixedWidth(160)
        self.probe_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.probe_button.clicked.connect(self._probe_sdr)
        self.sdr_panel.add(self.probe_button)
        self.sdr_panel.body.addStretch(1)
        bottom.addWidget(self.sdr_panel, 1)

        self.diag_panel = Panel("Diagnostics", "APPLICATION AND PATHS")
        self.diag_rows = {
            "app": KeyValueRow("Application", f"{APP_NAME} {APP_VERSION}"),
            "platform": KeyValueRow("Platform", f"{platform.system()} {platform.release()}"),
            "python": KeyValueRow("Python", sys.version.split()[0]),
            "backend": KeyValueRow("Scan backend", "\u2014"),
            "error": KeyValueRow("Last backend error", "none"),
            "log": KeyValueRow("Log directory", str(log_dir())),
            "data": KeyValueRow("Data directory", str(data_dir())),
        }
        for row in self.diag_rows.values():
            self.diag_panel.add(row)
        self.copy_button = QPushButton("  Copy diagnostics")
        self.copy_button.setObjectName("Ghost")
        self.copy_button.setFixedHeight(26)
        self.copy_button.setFixedWidth(160)
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.clicked.connect(self._copy)
        self.diag_panel.add(self.copy_button)
        self.diag_panel.body.addStretch(1)
        bottom.addWidget(self.diag_panel, 1)

        root.addLayout(bottom, 1)

        self.refresh_adapters()
        self._probe_sdr()

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self.refresh_adapters()
        self._probe_sdr()

    def refresh_adapters(self) -> None:
        adapters = self.ctx.adapters.adapters
        selected = self.ctx.adapters.selected
        self.adapter_list.set_adapters(adapters, selected)
        self.list_badge.setText(str(len(adapters)))
        self._show_adapter(selected)
        self.diag_rows["backend"].set_value(
            self.ctx.adapters.backend().label if adapters else "no backend selected"
        )
        self.diag_rows["error"].set_value(self.ctx.adapters.last_error or "none")

        if not adapters:
            self.detail_badge.setText("DEMO FALLBACK")
            self.detail_badge.setStyleSheet(
                f"color: {PALETTE['yellow']}; background: {rgba(PALETTE['yellow'], 0.10)};"
                f" border: 1px solid {rgba(PALETTE['yellow'], 0.34)}; border-radius: 7px; padding: 1px 7px;"
            )
            self.detail_notes.setText(
                "No wireless adapter was detected. On Linux install 'iw' and NetworkManager, or enable "
                "demonstration mode in Settings to explore the interface with simulated traffic."
            )
            return

    # ------------------------------------------------------------------
    def _refresh_adapters(self) -> None:
        if self._task is not None:
            return
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("  Detecting\u2026")
        task = Task(self.ctx.adapters.detect)
        task.signals.done.connect(self._detected)
        task.signals.failed.connect(self._detect_failed)
        self._task = task
        QThreadPool.globalInstance().start(task)

    def _detected(self, adapters) -> None:
        self._task = None
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("  Refresh")
        self.refresh_adapters()
        if not adapters:
            self.notice.show_message(
                "No wireless adapters were detected. Demonstration mode keeps the UI usable.",
                "warning",
                "Open Settings",
            )
            try:
                self.notice.action_triggered.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.notice.action_triggered.connect(lambda: bus.navigate.emit("settings"))
            self.notice.setVisible(True)
        else:
            self.notice.setVisible(False)

    def _detect_failed(self, message: str) -> None:
        self._task = None
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("  Refresh")
        self.notice.show_message(f"Adapter detection failed: {message}", "error", "Open Settings")
        try:
            self.notice.action_triggered.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.notice.action_triggered.connect(lambda: bus.navigate.emit("settings"))
        self.notice.setVisible(True)

    # ------------------------------------------------------------------
    def _select(self, interface: str) -> None:
        adapter = self.ctx.adapters.select(interface)
        if adapter is None:
            return
        self._show_adapter(adapter)
        self.adapter_list.set_adapters(self.ctx.adapters.adapters, adapter)

    def _show_adapter(self, adapter: AdapterInfo | None) -> None:
        self._adapter = adapter
        if adapter is None:
            for row in self.detail_rows.values():
                row.set_value("\u2014")
            self.detail_badge.setText("NO ADAPTER")
            self.detail_notes.setText("")
            return
        self.detail_badge.setText("DEMO" if adapter.is_demo else "HARDWARE")
        color = PALETTE["yellow"] if adapter.is_demo else PALETTE["green"]
        self.detail_badge.setStyleSheet(
            f"color: {color}; background: {rgba(color, 0.10)};"
            f" border: 1px solid {rgba(color, 0.34)}; border-radius: 7px; padding: 1px 7px;"
        )
        self.detail_rows["interface"].set_value(adapter.interface)
        self.detail_rows["name"].set_value(adapter.name)
        self.detail_rows["vendor"].set_value(adapter.vendor)
        self.detail_rows["chipset"].set_value(adapter.chipset)
        self.detail_rows["driver"].set_value(adapter.driver)
        self.detail_rows["version"].set_value(adapter.driver_version)
        self.detail_rows["backend"].set_value(adapter.backend)
        self.detail_rows["bands"].set_value(adapter.band_labels)
        widths = ", ".join(f"{w} MHz" for w in adapter.widths) if adapter.widths else "unknown"
        self.detail_rows["widths"].set_value(widths)
        self.detail_rows["monitor"].set_value(
            "supported", PALETTE["green"] if adapter.monitor_capable else PALETTE["muted"]
        )
        self.detail_rows["fft"].set_value(
            "SDR present" if adapter.supports_fft else "no SDR",
            PALETTE["green"] if adapter.supports_fft else PALETTE["muted"],
        )
        self.detail_rows["source"].set_value(
            "simulated" if adapter.is_demo else "hardware scan",
            PALETTE["yellow"] if adapter.is_demo else PALETTE["cyan"],
        )
        notes = "\n".join(f"\u2022 {note}" for note in adapter.notes) if adapter.notes else ""
        self.detail_notes.setText(notes)

    # ------------------------------------------------------------------
    def _probe_sdr(self) -> None:
        available, reason = self.ctx.sdr.probe()
        devices = self.ctx.sdr.devices
        if available:
            self.sdr_badge.setText("READY")
            self.sdr_badge.setStyleSheet(
                f"color: {PALETTE['green']}; background: {rgba(PALETTE['green'], 0.10)};"
                f" border: 1px solid {rgba(PALETTE['green'], 0.34)}; border-radius: 7px; padding: 1px 7px;"
            )
            self.sdr_status.setText("SoapySDR ready")
            self.sdr_status.setStyleSheet(f"color: {PALETTE['green']}; background: transparent;")
            self.sdr_reason.setText(
                "Raw FFT traces are available from the SDR device. Wi-Fi scan curves remain separate "
                "channel-shaped visualisations."
            )
            self.sdr_devices.setText(
                "\n".join(f"{device.driver}: {device.label}" for device in devices) or "No devices reported."
            )
        else:
            self.sdr_badge.setText("NOT AVAILABLE")
            self.sdr_badge.setStyleSheet(
                f"color: {PALETTE['muted']}; background: {rgba(PALETTE['muted'], 0.08)};"
                f" border: 1px solid {rgba(PALETTE['muted'], 0.28)}; border-radius: 7px; padding: 1px 7px;"
            )
            self.sdr_status.setText("No SDR detected")
            self.sdr_status.setStyleSheet(f"color: {PALETTE['muted']}; background: transparent;")
            self.sdr_reason.setText(
                "Wi-Fi curves in this application are channel-shaped visualisations built from scan data, "
                "not measured RF. Live FFT traces require a supported SoapySDR device."
            )
            self.sdr_devices.setText(reason or "SoapySDR bindings are not installed.")

    # ------------------------------------------------------------------
    def _copy(self) -> None:
        lines = [
            f"{APP_NAME} {APP_VERSION}",
            f"Platform: {platform.system()} {platform.release()}",
            f"Python: {sys.version.split()[0]}",
            f"Backend: {self.ctx.adapters.backend().label}",
            f"Adapters: {len(self.ctx.adapters.adapters)}",
            f"Last error: {self.ctx.adapters.last_error or 'none'}",
            f"Logs: {log_dir()}",
            f"Data: {data_dir()}",
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        QApplication.clipboard().setText("\n".join(lines))
        self.notice.show_message("Diagnostics copied to the clipboard.", "good", "")
        self.notice.setVisible(True)
