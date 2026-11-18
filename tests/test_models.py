"""Domain model behaviour: merging observations and derived properties."""

from __future__ import annotations

import time

from wifispectrum.core.bands import Band
from wifispectrum.core.models import AccessPoint, ScanSnapshot, unique_aps


def make(bssid: str, rssi: int, ssid: str = "HomeNet") -> AccessPoint:
    return AccessPoint(bssid=bssid, ssid=ssid, channel=6, frequency_mhz=2437, rssi=rssi)


def test_unique_aps_keeps_latest_observation() -> None:
    older = make("aa:bb:cc:dd:ee:ff", -70)
    newer = make("aa:bb:cc:dd:ee:ff", -55)
    newer.last_seen = older.last_seen + 5
    merged = unique_aps([older, newer])
    assert len(merged) == 1
    assert merged[0].rssi == -55
    assert merged[0].first_seen == older.first_seen


def test_hidden_network_gets_placeholder_ssid() -> None:
    item = AccessPoint(bssid="aa:bb:cc:dd:ee:ff", ssid="", channel=11, frequency_mhz=2462)
    assert item.hidden is True
    assert item.display_ssid == "<hidden>"


def test_snapshot_helpers() -> None:
    aps = [make("aa:bb:cc:dd:ee:01", -50), make("aa:bb:cc:dd:ee:02", -30)]
    snapshot = ScanSnapshot(aps=aps, timestamp=time.time(), demo=True)
    assert snapshot.total == 2
    assert snapshot.strongest is not None and snapshot.strongest.rssi == -30
    assert snapshot.channels_in_use(Band.GHZ_24) == [6]
    assert snapshot.counts_by_channel(Band.GHZ_24) == {6: 2}
    assert snapshot.demo is True
