"""Application-wide constants, palette and branding.

The palette is the single source of truth for both the QSS stylesheet and the
custom-painted widgets (spectrum curves, waterfall palettes, charts).
"""

from __future__ import annotations

APP_NAME = "WiFi Spectrum Studio"
APP_SHORT_NAME = "Spectrum Studio"
APP_SUBTITLE = "Analyze \u2022 Monitor \u2022 Optimize"
APP_TAGLINE = "Professional Wireless Analysis Tool"
APP_VERSION = "1.0.0"
APP_ORG = "WiFi Spectrum Studio"
APP_DOMAIN = "wifispectrum.studio"

# ---------------------------------------------------------------------------
# Colour palette (exact values from the design specification)
# ---------------------------------------------------------------------------
PALETTE = {
    "bg": "#07111B",
    "sidebar": "#091725",
    "panel": "#0D1C2A",
    "panel_alt": "#112536",
    "border": "#17465B",
    "cyan": "#00D9F5",
    "cyan_bright": "#00BDEB",
    "blue": "#168BFF",
    "green": "#00E89A",
    "yellow": "#FFC247",
    "orange": "#FF963D",
    "purple": "#C34BFF",
    "text": "#EAF5FC",
    "text_secondary": "#91A8BA",
    "muted": "#647F91",
    "pink": "#FF5FA2",
    "red": "#FF5C7A",
}

# Per-network curve colours (deterministic, one identifiable colour per AP)
CURVE_COLORS = [
    "#00E89A",  # green
    "#00D9F5",  # cyan
    "#168BFF",  # blue
    "#FF963D",  # orange
    "#C34BFF",  # purple
    "#FF5FA2",  # pink
    "#FFC247",  # yellow
    "#4FE3C1",  # mint
    "#7FA8FF",  # periwinkle
    "#B7F35A",  # lime
]

# Band accents used across charts and badges
BAND_COLORS = {
    "2.4": "#00E89A",
    "5": "#00D9F5",
    "6": "#C34BFF",
}

SEVERITY_COLORS = {
    "good": "#00E89A",
    "info": "#00D9F5",
    "warning": "#FFC247",
    "critical": "#FF5C7A",
}

# ---------------------------------------------------------------------------
# Operational tuning defaults (overridable through Settings)
# ---------------------------------------------------------------------------
DEFAULT_SCAN_INTERVAL_MS = 2000
DEFAULT_GRAPH_FPS = 30
DEFAULT_WATERFALL_FPS = 20
DEFAULT_HISTORY_MINUTES = 30
DEFAULT_RETENTION_DAYS = 30

# Signal quality thresholds in dBm
RSSI_EXCELLENT = -50
RSSI_GOOD = -60
RSSI_FAIR = -70
RSSI_WEAK = -80

GRAPH_FLOOR_DBM = -100.0

NAV_ITEMS = [
    ("dashboard", "Dashboard"),
    ("spectrum", "Live Spectrum"),
    ("analyzer", "Channel Analyzer"),
    ("discovery", "Network Discovery"),
    ("signal", "Signal Monitor"),
    ("frequency", "Frequency Explorer"),
    ("history", "History & Reports"),
    ("hardware", "Hardware"),
    ("settings", "Settings"),
]


def rssi_quality(rssi: int | None) -> str:
    if rssi is None:
        return "unknown"
    if rssi >= RSSI_EXCELLENT:
        return "excellent"
    if rssi >= RSSI_GOOD:
        return "good"
    if rssi >= RSSI_FAIR:
        return "fair"
    if rssi >= RSSI_WEAK:
        return "weak"
    return "poor"


def rssi_color(rssi: int | None) -> str:
    quality = rssi_quality(rssi)
    return {
        "excellent": PALETTE["green"],
        "good": PALETTE["cyan"],
        "fair": PALETTE["yellow"],
        "weak": PALETTE["orange"],
        "poor": PALETTE["red"],
    }.get(quality, PALETTE["muted"])
