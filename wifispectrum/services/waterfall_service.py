"""Waterfall data model: scrolling observation rows + display palettes.

Wi-Fi mode: each row is built from the access points observed in one scan.
SDR mode: each row is an actual FFT power vector supplied by the SDR service.
The widget always labels which kind of data is being shown.
"""

from __future__ import annotations

import numpy as np

from ..core import channels
from ..core.constants import GRAPH_FLOOR_DBM
from ..core.models import AccessPoint, Band

PALETTES: dict[str, list[str]] = {
    # Theme-native ramp: stays dark for weak signals, resolves to cyan/ice.
    "Spectrum": ["#04101A", "#082137", "#0B3C58", "#0E617E", "#00A2C4", "#00D9F5", "#7CEFD8", "#EAFDFF"],
    "Inferno": ["#050416", "#1B0C41", "#4A0C6B", "#781C6D", "#A52C60", "#CF4446", "#ED6925", "#FBB61A", "#FCFFA4"],
    "Ice": ["#030B14", "#0A2338", "#124A63", "#1C7E9B", "#38C6E0", "#8EEBFA", "#E8FDFF"],
    "Viridis": ["#08131F", "#21335C", "#2A6E7A", "#2E9E6B", "#7BC96F", "#D7E36A", "#FDE725"],
    "Amber": ["#0A0A12", "#2A1508", "#7A3208", "#D06310", "#FF963D", "#FFC247", "#FFF3C4"],
}


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def build_lut(name: str) -> np.ndarray:
    stops = PALETTES.get(name, PALETTES["Inferno"])
    colors = np.array([_hex_to_rgb(c) for c in stops], dtype=np.float32)
    positions = np.linspace(0.0, 1.0, len(stops))
    x = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for channel in range(3):
        lut[:, channel] = np.interp(x, positions, colors[:, channel]).astype(np.uint8)
    return lut


class WaterfallService:
    def __init__(self, rows: int = 180, bins: int = 640):
        self.rows = rows
        self.bins = bins
        self._matrix = np.zeros((rows, bins), dtype=np.float32)
        self._palette = "Spectrum"
        self._lut = build_lut(self._palette)

    def is_empty(self) -> bool:
        return float(self._matrix.max()) <= 0.001

    # -- configuration -----------------------------------------------------
    def set_palette(self, name: str) -> None:
        if name in PALETTES:
            self._palette = name
            self._lut = build_lut(name)

    @property
    def palette(self) -> str:
        return self._palette

    def reset(self) -> None:
        self._matrix.fill(0.0)

    # -- data --------------------------------------------------------------
    def push_row(self, row: np.ndarray) -> None:
        row = np.clip(row.astype(np.float32, copy=False), 0.0, 1.0)
        if row.shape[0] != self.bins:
            row = np.interp(
                np.linspace(0, row.shape[0] - 1, self.bins),
                np.arange(row.shape[0]),
                row,
            ).astype(np.float32)
        self._matrix = np.roll(self._matrix, 1, axis=0)
        self._matrix[0] = row

    def row_from_aps(self, aps: list[AccessPoint], band: Band, floor: float = GRAPH_FLOOR_DBM) -> np.ndarray:
        """Build one display row from the observed access points in a band.

        Each network contributes a smooth, channel-shaped energy profile built
        from its channel centre and width. This is a visualisation of observed
        channel occupancy - it is not a measured RF power envelope.
        """
        lo, hi = channels.band_bounds(band)
        freqs = np.linspace(lo, hi, self.bins, dtype=np.float32)
        row = np.zeros(self.bins, dtype=np.float32)
        for ap in aps:
            if ap.band is not band:
                continue
            centre = channels.channel_to_freq(band, ap.channel)
            if not centre:
                continue
            width = max(20.0, float(ap.width_mhz or 20))
            sigma = max(4.0, width / 2.7)
            weight = float(np.clip((ap.rssi - floor) / (-30.0 - floor), 0.0, 1.0))
            amplitude = 0.10 + 0.80 * (weight**1.6)
            profile = np.exp(-0.5 * ((freqs - centre) / sigma) ** 2)
            # Slightly broaden the crown so a channel reads as a plateau with
            # soft shoulders rather than a needle.
            profile = np.power(profile, 0.8)
            row = np.maximum(row, (amplitude * profile).astype(np.float32))
        # Display-only texture; a fraction of a percent, never presented as noise.
        row += np.random.random(self.bins).astype(np.float32) * 0.006
        return np.clip(row, 0.0, 1.0)

    def row_from_fft(self, power_db: np.ndarray, freq_lo: float, freq_hi: float, band: Band) -> np.ndarray:
        lo, hi = channels.band_bounds(band)
        src = np.asarray(power_db, dtype=np.float32)
        if src.size < 2:
            return np.zeros(self.bins, dtype=np.float32)
        src_freqs = np.linspace(freq_lo, freq_hi, src.size)
        targets = np.linspace(lo, hi, self.bins)
        db = np.interp(targets, src_freqs, src, left=-120.0, right=-120.0)
        return np.clip((db + 105.0) / 80.0, 0.0, 1.0)

    # -- output ------------------------------------------------------------
    @property
    def matrix(self) -> np.ndarray:
        return self._matrix

    def rgb(self) -> np.ndarray:
        idx = (self._matrix * 255.0).astype(np.uint8)
        return self._lut[idx]
