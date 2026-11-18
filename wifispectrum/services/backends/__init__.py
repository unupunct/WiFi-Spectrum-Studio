"""Backends: Linux (iw/nl80211 via NetworkManager), Windows (netsh), demo."""

from __future__ import annotations

from ...core.platform import is_linux, is_windows
from .base import (  # noqa: F401
    NoAdapterError,
    PermissionDeniedError,
    ScanBackend,
    ScanError,
    ScanOutcome,
    UnsupportedError,
    run_command,
    vendor_for,
)
from .demo import DemoBackend
from .linux import LinuxBackend
from .windows import WindowsBackend


def select_backend(prefer_demo: bool = False) -> ScanBackend:
    """Pick the best backend for this host.

    Demo mode is *always* explicit; we never silently fall back to simulated
    data when real hardware is present but unreadable.
    """
    if prefer_demo:
        return DemoBackend()
    if is_linux():
        linux = LinuxBackend()
        if linux.available()[0]:
            return linux
    if is_windows():
        win = WindowsBackend()
        if win.available()[0]:
            return win
    return DemoBackend()
