"""Adapter detection + wireless scan orchestration (thread-safe)."""

from __future__ import annotations

import logging
import threading
import time

from ..core.models import AccessPoint, AdapterInfo, ScanSnapshot
from .backends import select_backend
from .backends.base import ScanBackend, ScanError
from .settings_service import SettingsService

log = logging.getLogger(__name__)


class AdapterDetectionService:
    """Detects wireless adapters and keeps the active selection."""

    def __init__(self, settings: SettingsService):
        self._settings = settings
        self._lock = threading.Lock()
        self._backend: ScanBackend | None = None
        self._adapters: list[AdapterInfo] = []
        self._selected: AdapterInfo | None = None
        self._last_error: str = ""

    # -- backend lifecycle -------------------------------------------------
    def backend(self) -> ScanBackend:
        demo = bool(self._settings.get("demo_mode", False))
        with self._lock:
            if self._backend is None or self._backend.is_demo != demo:
                self._backend = select_backend(prefer_demo=demo)
                log.info("Using scan backend: %s", self._backend.label)
            return self._backend

    @property
    def last_error(self) -> str:
        return self._last_error

    def detect(self) -> list[AdapterInfo]:
        backend = self.backend()
        try:
            adapters = backend.list_adapters()
            self._last_error = ""
        except ScanError as exc:
            self._last_error = str(exc)
            log.warning("Adapter detection failed: %s", exc)
            adapters = []

        self._adapters = adapters
        if adapters:
            wanted = self._settings.get("adapter", "")
            selected = next((a for a in adapters if a.interface == wanted), None)
            if selected is None:
                selected = next((a for a in adapters if not a.is_demo), adapters[0])
            self._selected = selected
            self._settings.set("adapter", selected.interface, persist=False)
        else:
            self._selected = None
        return adapters

    @property
    def adapters(self) -> list[AdapterInfo]:
        return list(self._adapters)

    @property
    def selected(self) -> AdapterInfo | None:
        return self._selected

    def select(self, interface: str) -> AdapterInfo | None:
        for adapter in self._adapters:
            if adapter.interface == interface:
                self._selected = adapter
                self._settings.set("adapter", interface)
                return adapter
        return None

    @property
    def is_demo(self) -> bool:
        backend = self._backend
        return bool(backend and backend.is_demo)


class WirelessScanService:
    """Executes scans and keeps a short-lived observation cache.

    The cache keeps an access point visible for a few seconds when a single
    scan misses it, which avoids a flickering UI without inventing data.
    """

    def __init__(self, adapters: AdapterDetectionService, settings: SettingsService):
        self._adapters = adapters
        self._settings = settings
        self._cache: dict[str, AccessPoint] = {}
        self._lock = threading.Lock()

    def scan(self, interface: str | None = None) -> ScanSnapshot:
        backend = self._adapters.backend()
        adapter = self._adapters.selected if interface is None else next(
            (a for a in self._adapters.adapters if a.interface == interface), None
        )
        iface = interface or (adapter.interface if adapter else None)
        started = time.perf_counter()
        outcome = backend.scan(iface)
        duration = outcome.duration_ms or (time.perf_counter() - started) * 1000.0
        now = time.time()

        merged: dict[str, AccessPoint] = {}
        with self._lock:
            for ap in outcome.aps:
                cached = self._cache.get(ap.bssid)
                if cached is not None:
                    ap.first_seen = cached.first_seen
                else:
                    ap.first_seen = now
                merged[ap.bssid] = ap

            # Keep recently seen networks that this scan missed (<= 12 s old).
            ttl = max(8.0, min(30.0, self._settings.get("scan_interval_ms", 2000) / 1000.0 * 5))
            for bssid, cached in self._cache.items():
                if bssid in merged:
                    continue
                if now - cached.last_seen <= ttl:
                    merged[bssid] = cached
            self._cache = dict(merged)

        snapshot = ScanSnapshot(
            aps=sorted(merged.values(), key=lambda ap: ap.rssi, reverse=True),
            timestamp=now,
            adapter=adapter or outcome.adapter,
            demo=bool(backend.is_demo),
            duration_ms=duration,
            backend=backend.name,
        )
        if outcome.warnings:
            log.debug("Scan warnings: %s", "; ".join(outcome.warnings))
        return snapshot

    def reset_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def known_networks(self) -> list[AccessPoint]:
        with self._lock:
            return list(self._cache.values())
