"""Persistent application settings backed by a JSON document."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from ..core.platform import config_dir, default_export_dir

log = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "adapter": "",
    "band": "2.4",
    "scan_interval_ms": 2000,
    "graph_fps": 30,
    "waterfall_fps": 20,
    "history_minutes": 30,
    "retention_days": 30,
    "export_dir": default_export_dir(),
    "rssi_good": -60,
    "rssi_weak": -80,
    "theme": "dark",
    "waterfall_palette": "Spectrum",
    "demo_mode": False,
    "notifications": True,
    "region": "WORLD",
    "auto_scan": True,
    "reduce_motion": False,
    "sdr_mode": False,
    "sdr_device": "",
    "window_geometry": "",
}


class SettingsService(QObject):
    changed = Signal(str, object)

    def __init__(self, path: Path | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._path = path or (config_dir() / "settings.json")
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    # -- persistence -------------------------------------------------------
    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> None:
        if not self._path.exists():
            self.save()
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8-sig"))
            if isinstance(raw, dict):
                merged = dict(DEFAULTS)
                merged.update({k: v for k, v in raw.items() if k in DEFAULTS})
                self._data = merged
        except (OSError, ValueError) as exc:
            log.warning("Could not read settings (%s); using defaults", exc)
            self._data = dict(DEFAULTS)

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
            os.replace(tmp, self._path)
        except OSError as exc:
            log.error("Could not save settings: %s", exc)

    # -- access ------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any, persist: bool = True) -> None:
        if self._data.get(key) == value:
            return
        self._data[key] = value
        if persist:
            self.save()
        self.changed.emit(key, value)

    def update(self, values: dict[str, Any]) -> None:
        changed = False
        for key, value in values.items():
            if self._data.get(key) != value:
                self._data[key] = value
                changed = True
                self.changed.emit(key, value)
        if changed:
            self.save()

    def reset(self) -> None:
        self._data = dict(DEFAULTS)
        self.save()
        for key, value in self._data.items():
            self.changed.emit(key, value)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)
