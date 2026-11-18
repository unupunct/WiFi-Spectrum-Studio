"""Backend parsers: iw scan output and netsh field extraction."""

from __future__ import annotations

from wifispectrum.core.bands import Band
from wifispectrum.services.backends.linux import _parse_scan
from wifispectrum.services.backends.windows import _fields, _parse_security, _percent_to_dbm

IW_SCAN = """BSS 3c:2e:ff:11:22:33(on wlan0) -- associated
    freq: 2412.0
    signal: -42.00 dBm
    SSID: HomeNet
    DS Parameter set: channel 1
    HT operation:
        * primary channel: 1
        * secondary channel offset: no secondary
        * channel width: 0 (20 MHz)
    RSN:     * Version: 1
         * Authentication suites: PSK

BSS 9c:5c:8e:aa:bb:cc(on wlan0)
    freq: 5180
    signal: -61.50 dBm
    SSID: OfficeWiFi-5G
    HT operation:
        * primary channel: 36
        * channel width: 2 (80 MHz)
    RSN:     * Version: 1
         * Authentication suites: 802.1X
    HE capabilities:

BSS 18:e8:29:de:ad:be(on wlan0)
    freq: 2437.0
    signal: -78.00 dBm
    SSID:
    DS Parameter set: channel 6
    capability: ESS Privacy ShortSlotTime (0x0411)
"""


def test_iw_scan_parses_networks() -> None:
    aps = {ap.bssid: ap for ap in _parse_scan(IW_SCAN)}
    assert len(aps) == 3

    home = aps["3c:2e:ff:11:22:33"]
    assert home.ssid == "HomeNet"
    assert home.channel == 1
    assert home.frequency_mhz == 2412
    assert home.width_mhz == 20
    assert home.rssi == -42
    assert home.security == "WPA2"
    assert home.band is Band.GHZ_24
    assert home.vendor == "Apple"

    office = aps["9c:5c:8e:aa:bb:cc"]
    assert office.band is Band.GHZ_5
    assert office.channel == 36
    assert office.width_mhz == 80
    assert office.rssi == -62
    assert office.security == "WPA2-Ent"
    assert office.phy == "802.11ax"

    hidden = aps["18:e8:29:de:ad:be"]
    assert hidden.hidden is True
    assert hidden.channel == 6
    assert hidden.security == "WEP"


def test_windows_percent_mapping_is_bounded() -> None:
    assert _percent_to_dbm(100) == -50
    assert _percent_to_dbm(0) == -100
    assert _percent_to_dbm(50) == -75
    assert _percent_to_dbm(140) == -50


def test_windows_fields_and_security() -> None:
    block = """    SSID                   : Cafe
    Authentication         : WPA2-Personal
    Encryption             : CCMP
    Signal                 : 82%
    Channel                : 11
"""
    fields = _fields(block)
    assert fields["SSID"] == "Cafe"
    assert fields["Signal"] == "82%"
    assert fields["Channel"] == "11"
    assert _parse_security(fields["Authentication"]) == "WPA2"
    assert _parse_security("Open") == "Open"
    assert _parse_security("WPA3-Enterprise") == "WPA3-Ent"
    assert _parse_security("WPA2-Enterprise") == "WPA2-Ent"
