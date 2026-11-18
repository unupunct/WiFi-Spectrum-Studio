"""Settings: persisted preferences for scanning, display, storage and SDR."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.constants import PALETTE
from ...core.events import bus
from ...core.platform import config_dir
from ..widgets.base import (
    ToggleSwitch,
    PageHeader,
    Panel,
    hline,
    label,
)
from ..widgets.notice import NoticeBar

PALETTES = ["Spectrum", "Inferno", "Ice", "Viridis", "Amber"]
REGION_HELP = {
    "WORLD": "Common worldwide plan: 1\u201313 (2.4 GHz), UNII-1/2A/2C/3 (5 GHz).",
    "US": "FCC plan: 1\u201311 (2.4 GHz), UNII-1/2A/2C/3 (5 GHz).",
    "EU": "ETSI plan: 1\u201313 (2.4 GHz), UNII-1/2A/2C (5 GHz).",
    "JP": "Japan plan: 1\u201314 (2.4 GHz), UNII-1/2A/2C (5 GHz).",
}


class SettingRow(QWidget):
    def __init__(self, title: str, detail: str, control: QWidget, parent: QWidget | None = None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 7, 0, 7)
        row.setSpacing(14)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        text.addWidget(label(title, 9.8, PALETTE["text"], 500, 0.05))
        self.detail_label = None
        if detail:
            self.detail_label = label(detail, 8.2, PALETTE["muted"], 400, 0.05, wrap=True)
            text.addWidget(self.detail_label)
        row.addLayout(text, 1)
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.control = control


class SettingsPage(QWidget):
    def __init__(self, ctx, parent: QWidget | None = None):
        super().__init__(parent)
        self.ctx = ctx
        self._syncing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(9)

        header = PageHeader(
            "Settings",
            "Preferences apply immediately and are stored in your user configuration",
        )
        self.path_label = label(str(config_dir() / "settings.json"), 8.2, PALETTE["muted"], 400, 0.1)
        header.add_action(self.path_label)
        self.reset_button = QPushButton("  Reset defaults")
        self.reset_button.setObjectName("Danger")
        self.reset_button.setFixedHeight(28)
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.clicked.connect(self._reset)
        header.add_action(self.reset_button)
        root.addWidget(header)

        self.notice = NoticeBar()
        root.addWidget(self.notice)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        column = QVBoxLayout(container)
        column.setContentsMargins(0, 0, 6, 0)
        column.setSpacing(9)

        # -- scanning ------------------------------------------------------
        self.interval = QComboBox()
        for value, text in ((1000, "1 second"), (2000, "2 seconds"), (3000, "3 seconds"),
                            (5000, "5 seconds"), (10000, "10 seconds")):
            self.interval.addItem(text, value)
        self.interval.setFixedWidth(150)
        self.interval.currentIndexChanged.connect(
            lambda: self._set("scan_interval_ms", self.interval.currentData())
        )
        self.auto_scan = ToggleSwitch()
        self.auto_scan.toggled.connect(lambda value: self._set("auto_scan", value))
        self.notifications = ToggleSwitch()
        self.notifications.toggled.connect(lambda value: self._set("notifications", value))

        scanning = Panel("Scanning", "BACKGROUND MONITOR")
        scanning.add(self._row("Scan interval", "How often the adapter is asked for a fresh scan.", self.interval))
        scanning.add(hline())
        scanning.add(self._row("Start monitoring automatically", "Begin scanning as soon as an adapter is ready.", self.auto_scan))
        scanning.add(hline())
        scanning.add(self._row("Desktop notifications", "Show a system notification when a scan fails or a channel becomes critical.", self.notifications))
        column.addWidget(scanning)

        # -- display -------------------------------------------------------
        self.palette = QComboBox()
        self.palette.addItems(PALETTES)
        self.palette.setFixedWidth(150)
        self.palette.currentTextChanged.connect(lambda value: self._set("waterfall_palette", value))
        self.reduce_motion = ToggleSwitch()
        self.reduce_motion.toggled.connect(lambda value: self._set("reduce_motion", value))
        self.region = QComboBox()
        for key in ("WORLD", "US", "EU", "JP"):
            self.region.addItem(key, key)
        self.region.setFixedWidth(150)
        self.region.currentIndexChanged.connect(self._on_region)

        display = Panel("Display", "VISUALS AND REGION")
        display.add(self._row("Waterfall palette", "Colour ramp for the observation timeline.", self.palette))
        display.add(hline())
        display.add(self._row("Reduce motion", "Disable glow pulses and slow down the spectrum refresh.", self.reduce_motion))
        display.add(hline())
        self.region_row = self._row("Regulatory region", REGION_HELP["WORLD"], self.region)
        display.add(self.region_row)
        column.addWidget(display)

        # -- storage -------------------------------------------------------
        self.history_minutes = QComboBox()
        for value in (5, 10, 30, 60):
            self.history_minutes.addItem(f"{value} minutes", value)
        self.history_minutes.setFixedWidth(150)
        self.history_minutes.currentIndexChanged.connect(
            lambda: self._set("history_minutes", self.history_minutes.currentData())
        )
        self.retention = QSpinBox()
        self.retention.setRange(1, 3650)
        self.retention.setSuffix(" days")
        self.retention.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.retention.setFixedWidth(150)
        self.retention.valueChanged.connect(lambda value: self._set("retention_days", value))
        self.export_dir = QLineEdit()
        self.export_dir.setFixedWidth(300)
        self.export_dir.editingFinished.connect(lambda: self._set("export_dir", self.export_dir.text().strip()))
        browse = QPushButton("Browse\u2026")
        browse.setObjectName("Ghost")
        browse.setFixedHeight(28)
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.clicked.connect(self._browse)
        export_row = QWidget()
        export_layout = QHBoxLayout(export_row)
        export_layout.setContentsMargins(0, 0, 0, 0)
        export_layout.setSpacing(6)
        export_layout.addWidget(self.export_dir)
        export_layout.addWidget(browse)

        storage = Panel("History & Storage", "SQLITE, RETENTION AND EXPORTS")
        storage.add(self._row("Signal history window", "How much per-network RSSI history the Signal Monitor keeps in memory.", self.history_minutes))
        storage.add(hline())
        storage.add(self._row("Retention", "Stored scans older than this are pruned on startup and periodically.", self.retention))
        storage.add(hline())
        storage.add(self._row("Export directory", "Reports, CSVs and signal logs are written here by default.", export_row))
        column.addWidget(storage)

        # -- demonstration & SDR ------------------------------------------
        self.demo_mode = ToggleSwitch()
        self.demo_mode.toggled.connect(lambda value: self._on_demo(value))
        self.sdr_mode = ToggleSwitch()
        self.sdr_mode.toggled.connect(lambda value: self._set("sdr_mode", value))
        self.sdr_device = QLineEdit()
        self.sdr_device.setPlaceholderText("first available device")
        self.sdr_device.setFixedWidth(240)
        self.sdr_device.editingFinished.connect(lambda: self._set("sdr_device", self.sdr_device.text().strip()))

        hardware = Panel("Hardware & Demonstration", "DATA SOURCE AND TRUE FFT")
        hardware.add(self._row(
            "Demonstration mode",
            "Use simulated access points when no wireless adapter is available. Every screen labels this data as simulated.",
            self.demo_mode,
        ))
        hardware.add(hline())
        hardware.add(self._row(
            "SDR / true FFT",
            "Only meaningful with SoapySDR hardware. Wi-Fi curves never claim to be measured RF.",
            self.sdr_mode,
        ))
        hardware.add(hline())
        hardware.add(self._row("Preferred SDR device", "Leave empty to use the first device reported by SoapySDR.", self.sdr_device))
        column.addWidget(hardware)
        column.addStretch(1)

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        ctx.settings.changed.connect(self._on_setting)
        ctx.adapters  # noqa: B018 - make sure the service exists before reading demo state
        self._sync()

    # ------------------------------------------------------------------
    def on_show(self) -> None:
        self._sync()

    # ------------------------------------------------------------------
    def _row(self, title: str, detail: str, control: QWidget) -> SettingRow:
        return SettingRow(title, detail, control)

    def _set(self, key: str, value) -> None:
        if self._syncing:
            return
        self.ctx.settings.set(key, value)

    def _on_setting(self, key: str, value) -> None:
        if key in ("scan_interval_ms", "waterfall_palette", "reduce_motion", "history_minutes",
                   "retention_days", "export_dir", "demo_mode", "sdr_mode", "sdr_device",
                   "region", "auto_scan", "notifications"):
            self._sync()

    def _sync(self) -> None:
        settings = self.ctx.settings
        self._syncing = True
        try:
            interval = int(settings.get("scan_interval_ms", 2000))
            index = self.interval.findData(interval)
            self.interval.setCurrentIndex(index if index >= 0 else 1)
            self.auto_scan.setChecked(bool(settings.get("auto_scan", True)))
            self.notifications.setChecked(bool(settings.get("notifications", True)))

            palette = str(settings.get("waterfall_palette", "Spectrum"))
            palette_index = self.palette.findText(palette)
            self.palette.setCurrentIndex(palette_index if palette_index >= 0 else 0)
            self.reduce_motion.setChecked(bool(settings.get("reduce_motion", False)))

            region = str(settings.get("region", "WORLD")).upper()
            region_index = self.region.findData(region)
            self.region.setCurrentIndex(region_index if region_index >= 0 else 0)
            if self.region_row.detail_label is not None:
                self.region_row.detail_label.setText(REGION_HELP.get(region, REGION_HELP["WORLD"]))

            minutes = int(settings.get("history_minutes", 30))
            minutes_index = self.history_minutes.findData(minutes)
            self.history_minutes.setCurrentIndex(minutes_index if minutes_index >= 0 else 2)
            self.retention.setValue(int(settings.get("retention_days", 30)))
            self.export_dir.setText(str(settings.get("export_dir", "")))

            self.demo_mode.setChecked(bool(settings.get("demo_mode", False)))
            self.sdr_mode.setChecked(bool(settings.get("sdr_mode", False)))
            self.sdr_device.setText(str(settings.get("sdr_device", "")))

            available, reason = self.ctx.sdr.probe()
            self.sdr_mode.setEnabled(available)
            self.sdr_device.setEnabled(available)
            if available:
                self.sdr_device.setPlaceholderText("first available device")
            else:
                self.sdr_device.setPlaceholderText(reason or "SoapySDR not installed")
        finally:
            self._syncing = False

    def _on_region(self) -> None:
        key = self.region.currentData()
        if not key:
            return
        self._set("region", key)

    def _on_demo(self, value: bool) -> None:
        if self._syncing:
            return
        self.ctx.settings.set("demo_mode", value)
        state = "enabled" if value else "disabled"
        self.notice.show_message(
            f"Demonstration mode {state}. "
            + ("Simulated access points are labelled throughout the UI." if value else "Returning to hardware scans."),
            "warning" if value else "good",
            "Open Live Spectrum",
        )
        try:
            self.notice.action_triggered.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.notice.action_triggered.connect(lambda: bus.navigate.emit("spectrum"))
        self.notice.setVisible(True)

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Choose export directory", self.export_dir.text() or str(Path.home())
        )
        if directory:
            self.export_dir.setText(directory)
            self._set("export_dir", directory)

    def _reset(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset settings",
            "Restore every preference to its default value? Scans and history are not deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.ctx.settings.reset()
        self._sync()
        self.notice.show_message("Settings restored to defaults.", "good", "")
        self.notice.setVisible(True)
