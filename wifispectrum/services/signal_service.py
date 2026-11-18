"""Per-access-point signal history for the Signal Monitor page."""

from __future__ import annotations

import csv
import math
import time
from collections import deque

from PySide6.QtCore import QObject, Signal

from ..core.models import ScanSnapshot
from .analysis_service import ChannelAnalysisService
from .settings_service import SettingsService


class SignalMonitoringService(QObject):
    updated = Signal()

    def __init__(self, settings: SettingsService, parent: QObject | None = None):
        super().__init__(parent)
        self._settings = settings
        self._tracked: list[str] = []
        self._history: dict[str, deque[tuple[float, int]]] = {}
        self._meta: dict[str, tuple[str, int]] = {}

    # -- selection ---------------------------------------------------------
    @property
    def tracked(self) -> list[str]:
        return list(self._tracked)

    def set_tracked(self, bssids: list[str]) -> None:
        self._tracked = list(dict.fromkeys(bssids))
        for bssid in self._tracked:
            self._history.setdefault(bssid, self._maxlen_deque())
        self.updated.emit()

    def track(self, bssid: str, ssid: str = "", channel: int = 0) -> None:
        if bssid not in self._tracked:
            self._tracked.append(bssid)
        self._meta[bssid] = (ssid, channel)
        self._history.setdefault(bssid, self._maxlen_deque())
        self.updated.emit()

    def untrack(self, bssid: str) -> None:
        if bssid in self._tracked:
            self._tracked.remove(bssid)
            self.updated.emit()

    def clear(self) -> None:
        for series in self._history.values():
            series.clear()
        self.updated.emit()

    def _maxlen_deque(self) -> deque[tuple[float, int]]:
        minutes = int(self._settings.get("history_minutes", 30))
        interval = max(0.5, self._settings.get("scan_interval_ms", 2000) / 1000.0)
        return deque(maxlen=max(60, int(minutes * 60 / interval)))

    # -- ingestion ---------------------------------------------------------
    def record(self, snapshot: ScanSnapshot) -> None:
        if not self._tracked:
            return
        by_bssid = {ap.bssid: ap for ap in snapshot.aps}
        for bssid in self._tracked:
            ap = by_bssid.get(bssid)
            if ap is None:
                continue
            self._meta[bssid] = (ap.display_ssid, ap.channel)
            series = self._history.setdefault(bssid, self._maxlen_deque())
            if series and snapshot.timestamp - series[-1][0] < 0.4:
                series[-1] = (snapshot.timestamp, ap.rssi)
            else:
                series.append((snapshot.timestamp, ap.rssi))
        self.updated.emit()

    # -- queries -----------------------------------------------------------
    def history(self, bssid: str) -> list[tuple[float, int]]:
        return list(self._history.get(bssid, ()))

    def meta(self, bssid: str) -> tuple[str, int]:
        return self._meta.get(bssid, (bssid, 0))

    def stats(self, bssid: str) -> dict:
        series = self._history.get(bssid, ())
        if not series:
            return {
                "current": None,
                "average": None,
                "minimum": None,
                "maximum": None,
                "stability": 0.0,
                "samples": 0,
                "spread": 0,
            }
        values = [rssi for _, rssi in series]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return {
            "current": values[-1],
            "average": round(mean, 1),
            "minimum": min(values),
            "maximum": max(values),
            "stability": ChannelAnalysisService.stability(list(series)),
            "samples": len(values),
            "spread": max(values) - min(values),
            "stdev": round(math.sqrt(variance), 2),
        }

    def export_csv(self, path: str) -> str:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["bssid", "ssid", "channel", "timestamp_iso", "timestamp_unix", "rssi_dbm"])
            for bssid in self._tracked:
                ssid, channel = self.meta(bssid)
                for ts, rssi in self.history(bssid):
                    writer.writerow([bssid, ssid, channel, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)), f"{ts:.3f}", rssi])
        return path
