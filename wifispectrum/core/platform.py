"""Paths, logging and small OS helpers."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


def config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        path = Path(base) / "WiFiSpectrumStudio"
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        path = Path(base) / "wifi-spectrum-studio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        path = Path(base) / "WiFiSpectrumStudio"
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        path = Path(base) / "wifi-spectrum-studio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def documents_dir() -> Path:
    candidate = Path.home() / "Documents"
    return candidate if candidate.exists() else Path.home()


def default_export_dir() -> str:
    return str(documents_dir() / "WiFi Spectrum Studio")


def setup_logging(verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return logging.getLogger("wifispectrum")

    formatter = logging.Formatter(
        "%(asctime)s  %(levelname)-7s %(name)-24s %(message)s", "%H:%M:%S"
    )
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    root.addHandler(console)

    try:
        file_handler = logging.FileHandler(log_dir() / "wifispectrum.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        pass

    root.setLevel(level)
    return logging.getLogger("wifispectrum")


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def is_windows() -> bool:
    return sys.platform.startswith("win")
