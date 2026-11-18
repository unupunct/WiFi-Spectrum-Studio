"""Lightweight application event bus.

Only *notification* signals live here. All heavy lifting happens inside the
services and background tasks; UI pages subscribe to these Qt signals.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class EventBus(QObject):
    #: A completed scan snapshot (models.ScanSnapshot)
    snapshot = Signal(object)
    #: Scan cycle started
    scan_started = Signal()
    #: Scan failed with a human readable message
    scan_failed = Signal(str)
    #: Monitoring state changed: "running" | "paused" | "stopped" | "error"
    monitor_state = Signal(str)
    #: Adapter list refreshed
    adapters_changed = Signal(object)
    #: Selected adapter changed (models.AdapterInfo or None)
    adapter_changed = Signal(object)
    #: Status-bar text / operation update
    status = Signal(str)
    #: Settings key changed
    setting_changed = Signal(str, object)
    #: Background task progress (label, percent)
    progress = Signal(str, int)
    #: Navigation request from a page/widget
    navigate = Signal(str)
    #: Ask the app to open the detail drawer for a BSSID
    inspect_network = Signal(str)
    #: Non-fatal but user-visible problem
    notice = Signal(str, str)  # severity, message


bus = EventBus()
