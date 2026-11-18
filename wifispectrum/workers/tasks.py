"""Background task primitives (QRunnable based)."""

from __future__ import annotations

import logging
import traceback

from PySide6.QtCore import QObject, QRunnable, Signal

log = logging.getLogger(__name__)


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    finished = Signal()


class Task(QRunnable):
    """Runs a callable on the global thread pool and reports back via signals."""

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = TaskSignals()
        self.setAutoDelete(True)

    def run(self) -> None:  # pragma: no cover - executed on worker thread
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            log.debug("Background task failed: %s\n%s", exc, traceback.format_exc())
            self.signals.failed.emit(str(exc))
        else:
            self.signals.done.emit(result)
        finally:
            self.signals.finished.emit()
