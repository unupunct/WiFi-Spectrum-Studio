"""Main window: persistent chrome, navigation, live wiring and inspection drawer."""

from __future__ import annotations

import importlib
import logging

from PySide6.QtCore import QThreadPool, QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.constants import APP_NAME, APP_TAGLINE, NAV_ITEMS, PALETTE
from ..core.events import bus
from ..core.models import Band
from ..workers.tasks import Task
from .widgets.bottom_bar import BottomBar
from .widgets.drawer import NetworkDetailDrawer
from .widgets.sidebar import Sidebar
from .widgets.top_bar import TopBar
from .pages.placeholder import PlaceholderPage

log = logging.getLogger(__name__)

PAGE_MODULES = {
    "spectrum": ("live_spectrum", "LiveSpectrumPage"),
    "dashboard": ("dashboard", "DashboardPage"),
    "analyzer": ("channel_analyzer", "ChannelAnalyzerPage"),
    "discovery": ("network_discovery", "NetworkDiscoveryPage"),
    "signal": ("signal_monitor", "SignalMonitorPage"),
    "frequency": ("frequency_explorer", "FrequencyExplorerPage"),
    "history": ("history_reports", "HistoryReportsPage"),
    "hardware": ("hardware", "HardwarePage"),
    "settings": ("settings", "SettingsPage"),
}

# Pages with a dense fixed layout keep a minimum canvas size. Below it the
# page scrolls instead of clipping panels or squeezing labels.
PAGE_MINIMUMS: dict[str, tuple[int, int]] = {
    "spectrum": (1040, 800),
    "analyzer": (1320, 760),
}


class PageScroll(QScrollArea):
    """Scrollable canvas for dense pages.

    ``widgetResizable`` would silently rescale the page to its layout hint, so
    the geometry is managed here: the page always gets at least its design
    minimum and otherwise fills the viewport. Below the minimum the scrollbars
    keep every control reachable instead of clipping it.
    """

    def __init__(self, page: QWidget, minimum: tuple[int, int], parent: QWidget | None = None):
        super().__init__(parent)
        self._page = page
        page.setMinimumSize(*minimum)
        self.setWidgetResizable(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Scoped selectors only: an unscoped rule would cascade into the page
        # and override every child widget's background (buttons included).
        self.viewport().setObjectName("PageScrollViewport")
        self.setStyleSheet(
            f"QScrollArea, #PageScrollViewport {{ background: {PALETTE['bg']}; border: none; }}"
        )
        self.setWidget(page)
        self._fit()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        viewport = self.viewport().size()
        if viewport.width() > 0 and viewport.height() > 0:
            self._page.resize(viewport.expandedTo(self._page.minimumSize()))


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._last_snapshot = None
        self._drawer_bssid: str | None = None
        self._history_error_shown = False

        self.setWindowTitle(f"{APP_NAME} \u2014 {APP_TAGLINE}")
        self.setMinimumSize(1280, 780)
        self.resize(1600, 900)

        root = QWidget()
        root.setObjectName("Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.top_bar = TopBar()
        self.sidebar = Sidebar()
        self.stack = QStackedWidget()
        self.stack.setObjectName("Pages")

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.sidebar)
        body.addWidget(self.stack, 1)

        self.bottom_bar = BottomBar()
        outer.addWidget(self.top_bar)
        outer.addLayout(body, 1)
        outer.addWidget(self.bottom_bar)
        self.setCentralWidget(root)

        self.drawer = NetworkDetailDrawer(self.stack)
        self.drawer.track_requested.connect(self._track_network)

        self.pages: dict[str, QWidget] = {}
        self.containers: dict[str, QWidget] = {}
        self._build_pages()

        # signals
        self.sidebar.navigate.connect(self.navigate)
        self.top_bar.navigate.connect(self.navigate)
        bus.navigate.connect(self.navigate)
        bus.inspect_network.connect(self.show_network_detail)

        monitor = self.ctx.monitor
        monitor.snapshot_ready.connect(self._on_snapshot)
        monitor.scan_started.connect(self._on_scan_started)
        monitor.scan_failed.connect(self._on_scan_failed)
        monitor.state_changed.connect(self._on_state_changed)
        monitor.countdown.connect(self.bottom_bar.set_countdown)

        settings = self.ctx.settings
        settings.changed.connect(self._on_setting)
        self.ctx.adapters  # noqa: B018 - ensure service constructed

        self.top_bar.set_band(Band.parse(settings.get("band")))
        self.top_bar.set_state("stopped", "initialising")
        self.bottom_bar.set_state("stopped")
        self.bottom_bar.set_countdown(None)
        self.navigate("spectrum")

        QShortcut(QKeySequence("Ctrl+R"), self, activated=lambda: self.ctx.monitor.trigger_now())
        QShortcut(QKeySequence("F5"), self, activated=lambda: self.ctx.monitor.trigger_now())
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self.navigate("settings"))
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)
        QShortcut(QKeySequence("Esc"), self, activated=self.drawer.hide_drawer)
        for index, (key, _) in enumerate(NAV_ITEMS[:9], start=1):
            QShortcut(QKeySequence(f"Ctrl+{index}"), self, activated=lambda k=key: self.navigate(k))

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    def _build_pages(self) -> None:
        for key, title in NAV_ITEMS:
            module_name, class_name = PAGE_MODULES.get(key, ("", ""))
            page = None
            if module_name:
                try:
                    module = importlib.import_module(f".pages.{module_name}", package=__package__)
                    page_class = getattr(module, class_name)
                    page = page_class(self.ctx)
                except ImportError:
                    page = None
                except Exception as exc:  # noqa: BLE001 - page construction must not kill the app
                    log.exception("Failed to construct page %s: %s", key, exc)
                    page = None
            if page is None:
                page = PlaceholderPage(title, "This module is being connected to live services.")
            self.pages[key] = page
            container = self._wrap_page(key, page)
            self.containers[key] = container
            self.stack.addWidget(container)

    def _wrap_page(self, key: str, page: QWidget) -> QWidget:
        """Give dense pages a scrollable canvas so small windows do not clip."""
        minimum = PAGE_MINIMUMS.get(key)
        if minimum is None:
            return page
        return PageScroll(page, minimum)

    # ------------------------------------------------------------------
    # startup
    # ------------------------------------------------------------------
    def startup(self) -> None:
        self.bottom_bar.set_operation("Detecting wireless adapters\u2026")
        self.top_bar.set_adapter(None)
        task = Task(self.ctx.adapters.detect)
        task.signals.done.connect(self._adapters_detected)
        task.signals.failed.connect(self._adapter_detection_failed)
        self._startup_task = task
        QThreadPool.globalInstance().start(task)

    def _adapters_detected(self, adapters) -> None:
        adapter = self.ctx.adapters.selected
        self.top_bar.set_adapter(adapter)
        self.top_bar.set_demo(self.ctx.adapters.is_demo)
        self.bottom_bar.set_operation(
            f"Adapter ready \u2022 {adapter.interface} \u2022 {adapter.band_labels}"
            if adapter
            else "No wireless adapter detected"
        )
        if adapter is None:
            self.top_bar.set_state("error", "no adapter")
        else:
            self.top_bar.set_state("running", "starting")
        hardware_refresh = getattr(self.pages.get("hardware"), "refresh_adapters", None)
        if callable(hardware_refresh):
            hardware_refresh()

        if self.ctx.settings.get("auto_scan", True):
            QTimer.singleShot(250, self.ctx.monitor.start)
        else:
            self.ctx.monitor.trigger_now()

    def _adapter_detection_failed(self, message: str) -> None:
        self.top_bar.set_adapter(None)
        self.top_bar.set_state("error", "adapter error")
        self.bottom_bar.set_operation("Adapter detection failed")
        self.bottom_bar.set_error(message)
        self.ctx.monitor.trigger_now()

    # ------------------------------------------------------------------
    # monitoring
    # ------------------------------------------------------------------
    def _on_scan_started(self) -> None:
        self.bottom_bar.set_scanning(True)
        self.bottom_bar.set_operation("Scanning wireless channels\u2026")
        self.top_bar.set_state("running", "scanning")
        for page in self.pages.values():
            handler = getattr(page, "on_scan_started", None)
            if callable(handler):
                handler()

    def _on_snapshot(self, snapshot) -> None:
        self._last_snapshot = snapshot
        self.bottom_bar.set_scanning(False)
        self.bottom_bar.set_error(None)
        self.bottom_bar.set_last_update(snapshot.timestamp)
        self.bottom_bar.set_operation(
            f"Analysis complete \u2022 {snapshot.total} networks \u2022 {snapshot.duration_ms:.0f} ms"
        )
        self.bottom_bar.set_mode("DEMO SCAN" if snapshot.demo else "WI-FI SCAN",
                                 PALETTE["yellow"] if snapshot.demo else PALETTE["cyan"])
        adapter = snapshot.adapter or self.ctx.adapters.selected
        self.top_bar.set_adapter(adapter)
        self.top_bar.set_demo(snapshot.demo)
        if not snapshot.demo:
            self.top_bar.set_state("running", "scanning")

        band = Band.parse(self.ctx.settings.get("band"))
        self.sidebar.set_badge("spectrum", str(len(snapshot.aps)))
        self.sidebar.set_badge("discovery", str(snapshot.total))

        for page in self.pages.values():
            handler = getattr(page, "on_snapshot", None)
            if callable(handler):
                try:
                    handler(snapshot)
                except Exception:  # noqa: BLE001
                    log.exception("Page failed to handle snapshot")

        self.ctx.signals.record(snapshot)

        if self._drawer_bssid:
            ap = next((a for a in snapshot.aps if a.bssid == self._drawer_bssid), None)
            if ap is not None:
                self.drawer.set_network(ap)

        self._record_history(snapshot, band)

    def _record_history(self, snapshot, band: Band) -> None:
        history = self.ctx.history
        if history is None:
            return
        try:
            assessment = self.ctx.analysis.assess(snapshot, band)
            recommendation = None
            if assessment.recommendation:
                rec = assessment.recommendation
                recommendation = {
                    "band": band.key,
                    "channel": rec.channel,
                    "reason": rec.reason,
                    "confidence": rec.confidence,
                    "score": rec.score,
                    "networks": rec.networks,
                }
            history.record(snapshot, band.key, recommendation)
        except Exception as exc:  # noqa: BLE001 - persistence must never crash the UI
            log.warning("History write failed: %s", exc)
            if not self._history_error_shown:
                self._history_error_shown = True
                self.bottom_bar.set_error(f"History database error: {exc}")

    def _on_scan_failed(self, message: str) -> None:
        self.bottom_bar.set_scanning(False)
        self.bottom_bar.set_operation("Scan failed")
        self.bottom_bar.set_error(message)
        self.top_bar.set_state("error", "scan error")
        for page in self.pages.values():
            handler = getattr(page, "on_scan_error", None)
            if callable(handler):
                handler(message)

    def _on_state_changed(self, state: str) -> None:
        self.top_bar.set_state(state)
        self.bottom_bar.set_state(state)
        if state == "stopped":
            self.bottom_bar.set_countdown(None)
            self.bottom_bar.set_operation("Monitoring stopped")
            self.bottom_bar.set_scanning(False)

    # ------------------------------------------------------------------
    # navigation
    # ------------------------------------------------------------------
    def navigate(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(self.containers.get(key, page))
        self.sidebar.set_selected(key)
        self.top_bar.set_band(Band.parse(self.ctx.settings.get("band")))
        handler = getattr(page, "on_show", None)
        if callable(handler):
            try:
                handler()
            except Exception:  # noqa: BLE001
                log.exception("Page %s failed in on_show", key)

    def _focus_search(self) -> None:
        current = self.stack.currentWidget()
        for key, candidate in self.pages.items():
            if self.containers.get(key, candidate) is current:
                handler = getattr(candidate, "focus_search", None)
                if callable(handler):
                    handler()
                return

    # ------------------------------------------------------------------
    # network inspection
    # ------------------------------------------------------------------
    def show_network_detail(self, bssid: str) -> None:
        snapshot = self._last_snapshot
        ap = next((a for a in snapshot.aps if a.bssid == bssid), None) if snapshot else None
        if ap is None:
            return
        self._drawer_bssid = bssid
        self.drawer.show_for(ap)
        self.drawer.closed.connect(self._drawer_closed, Qt.ConnectionType.UniqueConnection)

    def _drawer_closed(self) -> None:
        self._drawer_bssid = None

    def _track_network(self, bssid: str) -> None:
        page = self.pages.get("signal")
        self.navigate("signal")
        handler = getattr(page, "track", None)
        if callable(handler):
            handler(bssid)
        self.drawer.hide_drawer()

    # ------------------------------------------------------------------
    # settings / lifecycle
    # ------------------------------------------------------------------
    def _on_setting(self, key: str, value) -> None:
        if key == "band":
            self.top_bar.set_band(Band.parse(value))
        elif key == "demo_mode":
            self.ctx.adapters.detect()
            self.ctx.scanner.reset_cache()
            self.top_bar.set_adapter(self.ctx.adapters.selected)
            self.top_bar.set_demo(bool(value))
            self.ctx.monitor.trigger_now()
        elif key == "region":
            self.ctx.analysis.region = str(value)
        elif key == "export_dir":
            self.ctx.reports.export_dir = __import__("pathlib").Path(str(value))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.drawer.isVisible():
            self.drawer.reposition()

    def closeEvent(self, event) -> None:
        try:
            self.ctx.settings.set("window_geometry", bytes(self.saveGeometry().toHex()).decode("ascii"))
        except Exception:  # noqa: BLE001
            pass
        self.ctx.monitor.stop()
        self.ctx.signals.clear()
        if self.ctx.history is not None:
            self.ctx.history.close()
        super().closeEvent(event)
