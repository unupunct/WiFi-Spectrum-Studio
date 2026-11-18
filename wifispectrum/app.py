"""Application bootstrap and dependency container."""

from __future__ import annotations

import logging
import sys
import traceback

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from .core.constants import APP_DOMAIN, APP_NAME, APP_ORG, APP_VERSION
from .core.events import bus
from .core.platform import setup_logging
from .services.analysis_service import ChannelAnalysisService
from .services.history_service import HistoryError, HistoryService
from .services.monitor import MonitorController
from .services.report_service import ReportService
from .services.scan_service import AdapterDetectionService, WirelessScanService
from .services.sdr_service import SDRService
from .services.settings_service import SettingsService
from .services.signal_service import SignalMonitoringService
from .services.waterfall_service import WaterfallService
from .ui import icons
from .ui.theme import apply_theme

log = logging.getLogger(__name__)


class ApplicationContext:
    """Constructs and owns every service used by the UI."""

    def __init__(self):
        self.settings = SettingsService()
        self.adapters = AdapterDetectionService(self.settings)
        self.scanner = WirelessScanService(self.adapters, self.settings)
        self.monitor = MonitorController(self.adapters, self.scanner, self.settings)
        self.analysis = ChannelAnalysisService(self.settings.get("region", "WORLD"))
        self.history: HistoryService | None
        self.history_error = ""
        try:
            self.history = HistoryService(retention_days=int(self.settings.get("retention_days", 30)))
        except HistoryError as exc:
            self.history = None
            self.history_error = str(exc)
            log.error("History unavailable: %s", exc)
        self.reports = ReportService(self.settings.get("export_dir"))
        self.signals = SignalMonitoringService(self.settings)
        self.sdr = SDRService()
        self.waterfall = WaterfallService()
        self.bus = bus


def _install_excepthook(app: QApplication) -> None:
    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        log.critical("Unhandled exception:\n%s", "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        try:
            QMessageBox.critical(
                None,
                f"{APP_NAME} \u2014 unexpected error",
                f"An unexpected error occurred:\n\n{exc_value}\n\nDetails were written to the application log.",
            )
        except Exception:  # noqa: BLE001
            pass

    sys.excepthook = hook


def run(argv: list[str] | None = None) -> int:
    setup_logging("--debug" in (argv or sys.argv))
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORG)
    app.setOrganizationDomain(APP_DOMAIN)
    app.setWindowIcon(icons.app_icon())
    apply_theme(app)
    _install_excepthook(app)

    from .ui.main_window import MainWindow

    ctx = ApplicationContext()
    window = MainWindow(ctx)
    geometry = ctx.settings.get("window_geometry", "")
    if geometry:
        try:
            window.restoreGeometry(bytes.fromhex(geometry))
        except ValueError:
            pass
    window.show()
    QTimer.singleShot(80, window.startup)

    if ctx.history is not None:
        ctx.history.prune(int(ctx.settings.get("retention_days", 30)))
        prune_timer = QTimer(app)
        prune_timer.setInterval(60 * 60 * 1000)
        prune_timer.timeout.connect(
            lambda: ctx.history and ctx.history.prune(int(ctx.settings.get("retention_days", 30)))
        )
        prune_timer.start()

    return app.exec()


def main(argv: list[str] | None = None) -> int:
    return run(argv)
