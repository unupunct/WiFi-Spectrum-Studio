"""Live monitoring controller: periodic background scans, never blocks the GUI."""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, QThreadPool, QTimer, Signal

from ..workers.tasks import Task
from .scan_service import AdapterDetectionService, WirelessScanService
from .settings_service import SettingsService

log = logging.getLogger(__name__)


class MonitorController(QObject):
    snapshot_ready = Signal(object)      # ScanSnapshot
    scan_started = Signal()
    scan_failed = Signal(str)
    state_changed = Signal(str)          # running | paused | stopped | error
    countdown = Signal(int)              # seconds until next refresh

    def __init__(
        self,
        adapters: AdapterDetectionService,
        scanner: WirelessScanService,
        settings: SettingsService,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._adapters = adapters
        self._scanner = scanner
        self._settings = settings
        self._pool = QThreadPool.globalInstance()
        self._busy = False
        self._state = "stopped"
        self._tasks: list[Task] = []
        self._last_snapshot = None
        self._last_error = ""
        self._next_due = 0.0

        self._timer = QTimer(self)
        self._timer.setSingleShot(False)
        self._timer.timeout.connect(self._tick)

        self._second = QTimer(self)
        self._second.setInterval(1000)
        self._second.timeout.connect(self._emit_countdown)

        self._settings.changed.connect(self._on_setting)

    # -- state -------------------------------------------------------------
    @property
    def state(self) -> str:
        return self._state

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def last_snapshot(self):
        return self._last_snapshot

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def interval_ms(self) -> int:
        return int(self._settings.get("scan_interval_ms", 2000))

    def _set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self.state_changed.emit(state)

    # -- lifecycle ---------------------------------------------------------
    def start(self, immediate: bool = True) -> None:
        self._timer.setInterval(max(500, self.interval_ms))
        self._timer.start()
        self._second.start()
        self._set_state("running")
        self._next_due = time.time() + (0.0 if immediate else self.interval_ms / 1000.0)
        if immediate:
            self.trigger_now()

    def pause(self) -> None:
        if self._state == "running":
            self._timer.stop()
            self._set_state("paused")

    def resume(self) -> None:
        if self._state in ("paused", "error", "stopped"):
            self._timer.start()
            self._set_state("running")
            self._next_due = time.time() + self.interval_ms / 1000.0

    def stop(self) -> None:
        self._timer.stop()
        self._second.stop()
        self._set_state("stopped")

    def trigger_now(self) -> None:
        self._next_due = time.time() + self.interval_ms / 1000.0
        self._tick(force=True)

    # -- scanning ----------------------------------------------------------
    def _tick(self, force: bool = False) -> None:
        if self._busy:
            return
        if not force and self._state != "running":
            return
        # Keep the countdown anchored to the scan cycle that is starting now.
        self._next_due = time.time() + self.interval_ms / 1000.0
        self._busy = True
        self.scan_started.emit()

        task = Task(self._scanner.scan, None)
        task.signals.done.connect(self._on_scan_done)
        task.signals.failed.connect(self._on_scan_failed)
        task.signals.finished.connect(lambda t=task: self._cleanup_task(t))
        self._tasks.append(task)
        self._pool.start(task)

    def _cleanup_task(self, task: Task) -> None:
        self._busy = False
        if task in self._tasks:
            self._tasks.remove(task)

    def _on_scan_done(self, snapshot) -> None:
        self._last_snapshot = snapshot
        self._last_error = ""
        self.snapshot_ready.emit(snapshot)
        if self._state == "error":
            self._set_state("running")

    def _on_scan_failed(self, message: str) -> None:
        self._last_error = message
        self.scan_failed.emit(message)
        if self._state == "running":
            self._set_state("error")

    # -- configuration -----------------------------------------------------
    def _on_setting(self, key: str, value) -> None:
        if key == "scan_interval_ms":
            self._timer.setInterval(max(500, int(value)))
            self._next_due = time.time() + int(value) / 1000.0
        elif key == "demo_mode":
            self._adapters.detect()
            self._scanner.reset_cache()
            self._last_snapshot = None

    def _emit_countdown(self) -> None:
        if self._state not in ("running",):
            return
        remaining = int(round(self._next_due - time.time()))
        self.countdown.emit(max(0, min(remaining, 99)))
