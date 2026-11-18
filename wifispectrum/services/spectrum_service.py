"""Spectrum curve geometry.

The curves are channel-shaped visualisations derived from real observed
channels, widths and RSSI. They are explicitly *not* continuous RF power
measurements - true FFT spectrum is only produced when SDR hardware is present.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core import channels
from ..core.constants import CURVE_COLORS, GRAPH_FLOOR_DBM
from ..core.models import AccessPoint, Band


@dataclass
class SpectrumCurve:
    bssid: str
    ssid: str
    color: str
    x: np.ndarray
    y: np.ndarray
    ap: AccessPoint
    peak_x: float
    peak_y: float

    @property
    def span(self) -> tuple[float, float]:
        return self.ap.span


def assign_colors(aps: list[AccessPoint]) -> dict[str, str]:
    """Stable colour per BSSID (sorted order => stable across scans)."""
    ordered = sorted({ap.bssid for ap in aps})
    return {bssid: CURVE_COLORS[i % len(CURVE_COLORS)] for i, bssid in enumerate(ordered)}


def shape(xs: np.ndarray, center: float, width_mhz: float) -> np.ndarray:
    """Smooth channel-shaped response (a display representation, not RF)."""
    half = max(10.0, width_mhz / 2.0)
    t = (xs - center) / half
    return np.exp(-0.5 * (t * 1.62) ** 2)


def build_curve(ap: AccessPoint, color: str, floor: float = GRAPH_FLOOR_DBM, points: int = 100) -> SpectrumCurve:
    half = max(10.0, ap.width_mhz / 2.0)
    lo = ap.frequency_mhz - half * 1.95
    hi = ap.frequency_mhz + half * 1.95
    xs = np.linspace(lo, hi, points)
    amp = max(1.0, ap.rssi - floor)
    ys = floor + amp * shape(xs, ap.frequency_mhz, ap.width_mhz)
    return SpectrumCurve(
        bssid=ap.bssid,
        ssid=ap.ssid,
        color=color,
        x=xs,
        y=ys,
        ap=ap,
        peak_x=float(ap.frequency_mhz),
        peak_y=float(ap.rssi),
    )


def build_curves(aps: list[AccessPoint], floor: float = GRAPH_FLOOR_DBM) -> tuple[list[SpectrumCurve], dict[str, str]]:
    colors = assign_colors(aps)
    curves = [build_curve(ap, colors[ap.bssid], floor) for ap in aps]
    curves.sort(key=lambda c: c.ap.rssi)  # strongest drawn last, on top
    return curves, colors


def envelope(aps: list[AccessPoint], band: Band, floor: float = GRAPH_FLOOR_DBM, step: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Maximum-hold composite of the channel shapes (still scan-derived)."""
    lo, hi = channels.band_bounds(band)
    xs = np.arange(lo, hi + step, step, dtype=float)
    if not aps:
        return xs, np.full_like(xs, floor)
    combined = np.full_like(xs, floor)
    for ap in aps:
        amp = max(1.0, ap.rssi - floor)
        ys = floor + amp * shape(xs, ap.frequency_mhz, ap.width_mhz)
        combined = np.maximum(combined, ys)
    return xs, combined


def legend_entries(aps: list[AccessPoint], colors: dict[str, str], limit: int = 8) -> list[tuple[str, str, int]]:
    ordered = sorted(aps, key=lambda ap: ap.rssi, reverse=True)[:limit]
    return [(ap.display_ssid, colors.get(ap.bssid, CURVE_COLORS[0]), ap.rssi) for ap in ordered]


def axis_ticks(band: Band) -> tuple[list[float], list[str]]:
    if band is Band.GHZ_24:
        freqs = [2400, 2420, 2440, 2460, 2480, 2500]
        return [float(f) for f in freqs], [str(f) for f in freqs]
    if band is Band.GHZ_5:
        freqs = list(range(5150, 5926, 100))
        return [float(f) for f in freqs], [str(f) for f in freqs]
    freqs = list(range(5925, 7126, 150))
    return [float(f) for f in freqs], [str(f) for f in freqs]
