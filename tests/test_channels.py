"""Channel maths, regulatory plans and recommendation scoring."""

from __future__ import annotations

import pytest

from wifispectrum.core import channels
from wifispectrum.core.bands import Band
from wifispectrum.core.models import AccessPoint


def ap(channel: int, band: Band = Band.GHZ_24, rssi: int = -60, width: int = 20) -> AccessPoint:
    return AccessPoint(
        bssid=f"00:11:22:33:44:{channel:02x}",
        ssid=f"net-{channel}",
        channel=channel,
        frequency_mhz=channels.channel_to_freq(band, channel),
        width_mhz=width,
        rssi=rssi,
    )


@pytest.mark.parametrize(
    ("band", "channel", "frequency"),
    [
        (Band.GHZ_24, 1, 2412),
        (Band.GHZ_24, 6, 2437),
        (Band.GHZ_24, 11, 2462),
        (Band.GHZ_5, 36, 5180),
        (Band.GHZ_5, 149, 5745),
        (Band.GHZ_6, 5, 5975),
        (Band.GHZ_6, 37, 6135),
    ],
)
def test_channel_frequency_roundtrip(band: Band, channel: int, frequency: int) -> None:
    assert channels.channel_to_freq(band, channel) == frequency
    assert channels.freq_to_channel(frequency) == channel


def test_regions_restrict_2ghz_channels() -> None:
    us = channels.band_channels(Band.GHZ_24, "US")
    jp = channels.band_channels(Band.GHZ_24, "JP")
    assert 1 in us and 11 in us
    assert 12 not in us and 13 not in us
    assert 14 in jp


def test_6ghz_psc_channels_are_every_80mhz() -> None:
    assert channels.PSC_CHANNELS_6[0] == 5
    assert all((channel - 5) % 16 == 0 for channel in channels.PSC_CHANNELS_6)


def test_recommendation_prefers_quiet_channel() -> None:
    quiet = channels.recommend_channel(Band.GHZ_24, [])
    assert quiet is not None
    assert quiet["channel"] in channels.NON_OVERLAP_24
    assert quiet["confidence"] in {"high", "medium", "low"}

    busy = [ap(1, rssi=-40), ap(1, rssi=-55), ap(6, rssi=-50)]
    best = channels.recommend_channel(Band.GHZ_24, busy)
    assert best is not None
    assert best["channel"] not in (1, 6)


def test_interference_grows_with_networks() -> None:
    empty = channels.interference_score(Band.GHZ_24, 1, [])
    one = channels.interference_score(Band.GHZ_24, 1, [ap(1)])
    two = channels.interference_score(Band.GHZ_24, 1, [ap(1), ap(1, rssi=-45)])
    assert empty == 0.0
    assert empty < one < two


def test_congestion_is_a_percentage() -> None:
    value = channels.congestion_pct([ap(1), ap(6), ap(11)], Band.GHZ_24)
    assert 0.0 <= value <= 100.0
    assert channels.congestion_pct([], Band.GHZ_24) == 0.0
