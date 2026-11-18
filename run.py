#!/usr/bin/env python3
"""Launcher for WiFi Spectrum Studio."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Linux/X11: keep Qt from forcing a specific scale when the user configured one.
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

from wifispectrum.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv))
