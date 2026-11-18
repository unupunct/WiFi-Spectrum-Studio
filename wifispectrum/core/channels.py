"""Regulatory-aware channel tables and pure channel math.

Every helper here is deterministic and side-effect free so it can be unit
tested and reused from background workers without Qt.
"""

from __future__ import annotations

from .bands import Band

# 2.4 GHz -------------------------------------------------------------------
_FREQ_24 = {
    1: 2412,
    2: 2417,
    3: 2422,
    4: 2427,
    5: 2432,
    6: 2437,
    7: 2442,
    8: 2447,
    9: 2452,
    10: 2457,
    11: 2462,
    12: 2467,
    13: 2472,
    14: 2484,
}

# 5 GHz ---------------------------------------------------------------------
_FREQ_5 = {
    32: 5160,
    36: 5180,
    40: 5200,
    44: 5220,
    48: 5240,
    52: 5260,
    56: 5280,
    60: 5300,
    64: 5320,
    68: 5340,
    96: 5480,
    100: 5500,
    104: 5520,
    108: 5540,
    112: 5560,
    116: 5580,
    120: 5600,
    124: 5620,
    128: 5640,
    132: 5660,
    136: 5680,
    140: 5700,
    144: 5720,
    149: 5745,
    153: 5765,
    157: 5785,
    161: 5805,
    165: 5825,
    169: 5845,
    173: 5865,
    177: 5885,
}

# Channel width -> centre offset for wide 5 GHz blocks is handled by the
# span calculation; widths listed here are what mainstream hardware exposes.
BAND_CHANNELS: dict[Band, dict[int, int]] = {
    Band.GHZ_24: _FREQ_24,
    Band.GHZ_5: _FREQ_5,
    # 6 GHz: 20 MHz channels are numbered 1, 5, 9 ... 233
    Band.GHZ_6: {ch: 5950 + 5 * ch for ch in range(1, 234, 4)},
}

BAND_WIDTHS: dict[Band, list[int]] = {
    Band.GHZ_24: [20, 40],
    Band.GHZ_5: [20, 40, 80, 160],
    Band.GHZ_6: [20, 40, 80, 160, 320],
}

# Simplified regulatory channel availability. Real deployments are governed by
# the driver/CRDA; the adapter probe is authoritative at runtime.
REGIONS = {
    "US": {Band.GHZ_24: range(1, 12), Band.GHZ_5: range(36, 166, 4), Band.GHZ_6: range(1, 234, 4)},
    "EU": {Band.GHZ_24: range(1, 14), Band.GHZ_5: list(range(36, 65, 4)) + list(range(100, 141, 4)), Band.GHZ_6: range(1, 234, 4)},
    "JP": {Band.GHZ_24: range(1, 15), Band.GHZ_5: list(range(36, 65, 4)) + list(range(100, 141, 4)), Band.GHZ_6: range(1, 234, 4)},
    "WORLD": {Band.GHZ_24: range(1, 14), Band.GHZ_5: list(range(36, 65, 4)) + list(range(100, 145, 4)) + list(range(149, 166, 4)), Band.GHZ_6: range(1, 234, 4)},
}

# 6 GHz preferred scanning channels (20 MHz, every 80 MHz)
PSC_CHANNELS_6 = [5 + 16 * i for i in range(15)]

# Non-overlapping 2.4 GHz channels in the common 1-11 plan
NON_OVERLAP_24 = (1, 6, 11)


def channel_to_freq(band: Band, channel: int) -> int:
    if band is Band.GHZ_6:
        return 5950 + 5 * channel
    return BAND_CHANNELS.get(band, _FREQ_24).get(channel, 0)


def freq_to_channel(mhz: int) -> int:
    """Best-effort channel number from a centre frequency."""
    for band in Band.all():
        table = BAND_CHANNELS[band]
        for ch, freq in table.items():
            if abs(freq - mhz) <= 2:
                return ch
    if 5925 <= mhz <= 7125:
        return max(1, int(round((mhz - 5950) / 5.0)))
    if 2400 <= mhz < 2500:
        return max(1, min(14, int(round((mhz - 2407) / 5.0))))
    if 5000 <= mhz < 5925:
        # 5 GHz channels sit on 5 MHz multiples of a 20 MHz raster
        return int(round((mhz - 5000) / 5.0))
    return 0


def band_channels(band: Band, region: str = "WORLD") -> list[int]:
    table = BAND_CHANNELS[band]
    allowed = REGIONS.get(region.upper(), REGIONS["WORLD"]).get(band)
    if not allowed:
        return sorted(table)
    allowed_set = set(allowed)
    return [ch for ch in sorted(table) if ch in allowed_set]


def band_bounds(band: Band) -> tuple[int, int]:
    if band is Band.GHZ_24:
        return 2400, 2500
    if band is Band.GHZ_5:
        return 5150, 5925
    return 5925, 7125


def band_span_mhz(band: Band) -> int:
    lo, hi = band_bounds(band)
    return hi - lo


def occupied_span(band: Band, channel: int, width_mhz: int) -> tuple[float, float]:
    """Return the frequency span a channel occupies for visualisation.

    This is a *channel-shaped representation* built from the observed channel
    and width. It is not a measured RF power envelope.
    """
    center = channel_to_freq(band, channel)
    if not center:
        return (0.0, 0.0)
    width = max(20, int(width_mhz or 20))
    lo, hi = band_bounds(band)
    return (max(lo, center - width / 2.0), min(hi, center + width / 2.0))


def overlap_mhz(span_a: tuple[float, float], span_b: tuple[float, float]) -> float:
    lo = max(span_a[0], span_b[0])
    hi = min(span_a[1], span_b[1])
    return max(0.0, hi - lo)


def rssi_weight(rssi: int) -> float:
    """Relative linear weight for a dBm value (0..1)."""
    # -100 dBm -> ~0.0, -30 dBm -> ~1.0, exponential in between.
    return max(0.0, min(1.0, (rssi + 100.0) / 70.0))


def congestion_pct(aps, band: Band, step_mhz: float = 5.0) -> float:
    """Network-density congestion estimate (not airtime utilisation).

    For every frequency bin in the band we take the strongest overlapping
    network's RSSI weight; the mean of that occupancy curve becomes a 0-100 %
    indicator of how much of the band is claimed by observed networks.
    """
    lo, hi = band_bounds(band)
    bins = int(round((hi - lo) / step_mhz))
    if bins <= 0:
        return 0.0
    occupancy = [0.0] * bins
    for ap in aps:
        if ap.band is not band:
            continue
        span_lo, span_hi = occupied_span(band, ap.channel, ap.width_mhz)
        if span_hi <= span_lo:
            continue
        weight = rssi_weight(ap.rssi)
        start = int(max(0, (span_lo - lo) / step_mhz))
        end = int(min(bins, (span_hi - lo) / step_mhz))
        for idx in range(start, end):
            if weight > occupancy[idx]:
                occupancy[idx] = weight
    if not occupancy:
        return 0.0
    return round(100.0 * sum(occupancy) / len(occupancy), 1)


def interference_score(band: Band, channel: int, aps, width_mhz: int = 20) -> float:
    """Sum of weighted overlap of every observed AP onto a candidate channel."""
    target = occupied_span(band, channel, width_mhz)
    score = 0.0
    for ap in aps:
        if ap.band is not band:
            continue
        overlap = overlap_mhz(target, ap.span)
        if overlap <= 0:
            continue
        score += (overlap / max(1.0, target[1] - target[0])) * rssi_weight(ap.rssi)
    return round(score, 3)


def recommend_channel(band: Band, aps, region: str = "WORLD", limit_channels: list[int] | None = None):
    """Return the quietest channel plus scored alternatives."""
    candidates = limit_channels or band_channels(band, region)
    if not candidates:
        return None
    scored = [(ch, interference_score(band, ch, aps)) for ch in candidates]
    scored.sort(key=lambda item: (item[1], item[0]))
    best_channel, best_score = scored[0]
    runner_up = scored[1][1] if len(scored) > 1 else best_score
    observations = sum(1 for ap in aps if ap.band is band)
    margin = runner_up - best_score

    if observations == 0:
        confidence = "low"
    elif margin >= 0.5 and observations >= 4:
        confidence = "high"
    elif margin >= 0.2:
        confidence = "medium"
    else:
        confidence = "low"

    if observations == 0:
        reason = "No networks observed in this band yet; the first channel of the band is suggested."
    elif best_score < 0.05:
        reason = "Effectively clear of every observed network in this band."
    elif margin >= 0.3:
        reason = "Lowest weighted overlap of all observed networks for this band."
    else:
        reason = "Least interfered option, but neighbouring channels are nearly as quiet."

    return {
        "channel": best_channel,
        "score": best_score,
        "confidence": confidence,
        "reason": reason,
        "networks": observations,
        "alternatives": [ch for ch, _ in scored[1:4]],
        "scored": scored,
    }


def channel_frequency_label(band: Band, channel: int) -> str:
    return f"{channel_to_freq(band, channel)} MHz"


def describe_width(width_mhz: int) -> str:
    return f"{width_mhz} MHz"
