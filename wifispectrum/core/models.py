"""Typed domain models shared by every service and UI page."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Iterable

from . import channels
from .bands import Band

__all__ = [
    "Band",
    "AccessPoint",
    "AdapterInfo",
    "ScanSnapshot",
    "Insight",
    "ChannelRecommendation",
    "ChannelAssessment",
    "unique_aps",
]


@dataclass
class AccessPoint:
    """A single observed BSS.

    All measurement fields come straight from the scan backend. Nothing in this
    model is interpolated: ``rssi`` is the observed signal level and
    ``width_mhz`` is the observed/nominal channel width.
    """

    bssid: str
    ssid: str
    channel: int = 0
    frequency_mhz: int = 0
    width_mhz: int = 20
    rssi: int = -100
    security: str = "Open"
    vendor: str = "Unknown"
    phy: str = ""
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    hidden: bool = False
    source: str = "scan"

    def __post_init__(self) -> None:
        if not self.frequency_mhz and self.channel:
            band = Band.from_frequency(channels.channel_to_freq(Band.GHZ_24, self.channel))
            # Only 2.4 GHz table is unambiguous without a band hint; callers
            # that know the band always supply the frequency.
            self.frequency_mhz = channels.channel_to_freq(band, self.channel)
        if not self.channel and self.frequency_mhz:
            self.channel = channels.freq_to_channel(self.frequency_mhz)
        if not self.ssid:
            self.hidden = True
            self.ssid = "<hidden>"

    # -- derived -----------------------------------------------------------
    @property
    def band(self) -> Band:
        return Band.from_frequency(self.frequency_mhz or 2412)

    @property
    def display_ssid(self) -> str:
        return self.ssid if self.ssid else "<hidden>"

    @property
    def span(self) -> tuple[float, float]:
        """Occupied frequency span derived from the channel width."""
        return channels.occupied_span(self.band, self.channel, self.width_mhz)

    @property
    def key(self) -> str:
        return self.bssid

    @property
    def age_s(self) -> float:
        return max(0.0, time.time() - self.last_seen)

    def merged(self, other: "AccessPoint") -> "AccessPoint":
        """Merge a newer observation into this one, keeping first-seen time."""
        return replace(
            self,
            ssid=other.ssid or self.ssid,
            channel=other.channel or self.channel,
            frequency_mhz=other.frequency_mhz or self.frequency_mhz,
            width_mhz=other.width_mhz or self.width_mhz,
            rssi=other.rssi,
            security=other.security or self.security,
            vendor=other.vendor or self.vendor,
            phy=other.phy or self.phy,
            last_seen=other.last_seen,
            hidden=other.hidden,
            source=other.source,
        )


@dataclass
class AdapterInfo:
    interface: str
    name: str = "Unknown adapter"
    vendor: str = "Unknown"
    chipset: str = "Unknown"
    driver: str = "Unknown"
    driver_version: str = "Unknown"
    bands: list[Band] = field(default_factory=list)
    widths: list[int] = field(default_factory=list)
    channels: dict[str, list[int]] = field(default_factory=dict)
    supports_fft: bool = False
    monitor_capable: bool = False
    backend: str = "unknown"
    notes: list[str] = field(default_factory=list)
    is_demo: bool = False

    @property
    def band_labels(self) -> str:
        return ", ".join(b.label for b in self.bands) if self.bands else "Unknown"

    @property
    def supported_bands(self) -> set[Band]:
        return set(self.bands) if self.bands else {Band.GHZ_24}

    def supports(self, band: Band) -> bool:
        return band in self.supported_bands

    def to_dict(self) -> dict:
        return {
            "interface": self.interface,
            "name": self.name,
            "vendor": self.vendor,
            "chipset": self.chipset,
            "driver": self.driver,
            "driver_version": self.driver_version,
            "bands": [b.value for b in self.bands],
            "widths": list(self.widths),
            "channels": {k: list(v) for k, v in self.channels.items()},
            "supports_fft": self.supports_fft,
            "monitor_capable": self.monitor_capable,
            "backend": self.backend,
            "notes": list(self.notes),
            "is_demo": self.is_demo,
        }


@dataclass
class ScanSnapshot:
    aps: list[AccessPoint]
    timestamp: float = field(default_factory=time.time)
    adapter: AdapterInfo | None = None
    demo: bool = False
    duration_ms: float = 0.0
    error: str | None = None
    backend: str = "unknown"

    def by_band(self, band: Band) -> list[AccessPoint]:
        return [ap for ap in self.aps if ap.band is band]

    @property
    def total(self) -> int:
        return len(self.aps)

    @property
    def strongest(self) -> AccessPoint | None:
        return max(self.aps, key=lambda ap: ap.rssi) if self.aps else None

    def channels_in_use(self, band: Band | None = None) -> list[int]:
        aps = self.aps if band is None else self.by_band(band)
        return sorted({ap.channel for ap in aps})

    def counts_by_channel(self, band: Band) -> dict[int, int]:
        counts: dict[int, int] = {}
        for ap in self.by_band(band):
            counts[ap.channel] = counts.get(ap.channel, 0) + 1
        return counts


@dataclass
class Insight:
    severity: str  # good | info | warning | critical
    title: str
    detail: str
    measurement: str = ""


@dataclass
class ChannelRecommendation:
    band: Band
    channel: int
    frequency_mhz: int
    reason: str
    networks: int
    confidence: str  # high | medium | low
    score: float
    alternatives: list[int] = field(default_factory=list)

    @property
    def confidence_pct(self) -> int:
        return {"high": 92, "medium": 74, "low": 55}.get(self.confidence, 50)


@dataclass
class ChannelAssessment:
    band: Band
    counts: dict[int, int]
    congestion_pct: float
    busiest_channel: int | None
    quietest_channel: int | None
    recommendation: ChannelRecommendation | None
    observations: int
    overlapping_pairs: int


def unique_aps(aps: Iterable[AccessPoint]) -> list[AccessPoint]:
    """De-duplicate an AP iterable by BSSID (last observation wins)."""
    out: dict[str, AccessPoint] = {}
    for ap in aps:
        existing = out.get(ap.bssid)
        out[ap.bssid] = ap if existing is None else existing.merged(ap)
    return list(out.values())
