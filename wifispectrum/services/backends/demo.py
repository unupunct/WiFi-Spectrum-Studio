"""Demo backend.

Simulated, clearly labelled observations used for demonstrations, screenshots
and UI development when no compatible hardware is present. The application
always marks these values as demo data in the top bar, waterfall legend and
status bar - never as measurements.
"""

from __future__ import annotations

import math
import random
import time

from ...core import channels
from ...core.models import AccessPoint, AdapterInfo, Band
from .base import ScanBackend, ScanOutcome

_BSSIDS = [
    ("3C:2E:FF", "Apple"),
    ("A4:C3:F0", "Intel"),
    ("F4:F2:6D", "TP-Link"),
    ("24:5A:4C", "Ubiquiti"),
    ("B0:BE:76", "TP-Link"),
    ("38:D5:47", "ASUSTek"),
    ("E4:F3:65", "Intel"),
    ("18:E8:29", "Ubiquiti"),
    ("50:C7:BF", "TP-Link"),
    ("9C:5C:8E", "ASUSTek"),
    ("D8:F1:5B", "Espressif"),
    ("F0:18:98", "Apple"),
]


class _DemoNetwork:
    __slots__ = ("ssid", "bssid", "vendor", "band", "channel", "width", "base_rssi", "security", "phy", "phase", "drift")

    def __init__(self, ssid, bssid, vendor, band, channel, width, base_rssi, security, phy):
        self.ssid = ssid
        self.bssid = bssid
        self.vendor = vendor
        self.band = band
        self.channel = channel
        self.width = width
        self.base_rssi = base_rssi
        self.security = security
        self.phy = phy
        self.phase = random.uniform(0, math.tau)
        self.drift = random.uniform(1.2, 3.4)


def _build_networks() -> list[_DemoNetwork]:
    specs = [
        # ssid, band, channel, width, base rssi, security, phy
        ("HomeNet", Band.GHZ_24, 1, 20, -32, "WPA2", "802.11ax"),
        ("OfficeWiFi", Band.GHZ_24, 6, 20, -48, "WPA2-Ent", "802.11ax"),
        ("Guest_Network", Band.GHZ_24, 11, 20, -62, "WPA2", "802.11n"),
        ("IoT-Devices", Band.GHZ_24, 11, 20, -67, "WPA2", "802.11n"),
        ("NETGEAR-55", Band.GHZ_24, 1, 40, -71, "WPA2", "802.11n"),
        ("DIRECT-3F-HP", Band.GHZ_24, 6, 20, -76, "WPA2", "802.11n"),
        ("FRITZ!Box 7590 QX", Band.GHZ_24, 9, 40, -80, "WPA3", "802.11ax"),
        ("xfinitywifi", Band.GHZ_24, 3, 20, -83, "Open", "802.11n"),
        ("HomeNet-5G", Band.GHZ_5, 36, 80, -41, "WPA2", "802.11ax"),
        ("OfficeWiFi-5G", Band.GHZ_5, 44, 80, -52, "WPA2-Ent", "802.11ax"),
        ("Ubiquiti-Lobby", Band.GHZ_5, 48, 80, -58, "WPA2", "802.11ac"),
        ("IoT-Devices-5G", Band.GHZ_5, 100, 40, -69, "WPA2", "802.11ax"),
        ("ASUS_80", Band.GHZ_5, 149, 80, -74, "WPA2", "802.11ac"),
        ("Cafe_Free_WiFi", Band.GHZ_5, 157, 20, -81, "Open", "802.11n"),
        ("HomeNet-6E", Band.GHZ_6, 37, 160, -46, "WPA3", "802.11be"),
        ("OfficeWiFi-6E", Band.GHZ_6, 69, 160, -59, "WPA3-Ent", "802.11be"),
        ("IoT-Devices-6G", Band.GHZ_6, 5, 40, -72, "WPA3", "802.11ax"),
    ]
    networks: list[_DemoNetwork] = []
    for index, (ssid, band, channel, width, rssi, security, phy) in enumerate(specs):
        oui, vendor = _BSSIDS[index % len(_BSSIDS)]
        suffix = ":".join(f"{random.randint(0, 255):02X}" for _ in range(3))
        networks.append(
            _DemoNetwork(ssid, f"{oui}:{suffix}", vendor, band, channel, width, rssi, security, phy)
        )
    return networks


class DemoBackend(ScanBackend):
    name = "demo"
    label = "Demonstration data (simulated)"
    is_demo = True

    def __init__(self) -> None:
        self._networks = _build_networks()
        self._started = time.time()

    def available(self) -> tuple[bool, str]:
        return True, ""

    def list_adapters(self) -> list[AdapterInfo]:
        return [
            AdapterInfo(
                interface="wlan0",
                name="Intel Wi-Fi 6E AX211 (demo)",
                vendor="Intel",
                chipset="AX211 / iwlwifi",
                driver="iwlwifi",
                driver_version="demo",
                bands=[Band.GHZ_24, Band.GHZ_5, Band.GHZ_6],
                widths=[20, 40, 80, 160, 320],
                channels={},
                supports_fft=False,
                monitor_capable=True,
                backend="demo",
                notes=[
                    "DEMO MODE: all observations in this session are simulated for interface "
                    "demonstration and are never presented as measurements.",
                ],
                is_demo=True,
            )
        ]

    def capabilities(self, interface: str) -> AdapterInfo | None:
        return self.list_adapters()[0]

    def scan(self, interface: str | None) -> ScanOutcome:
        started = time.perf_counter()
        now = time.time()
        elapsed = now - self._started
        aps: list[AccessPoint] = []
        for net in self._networks:
            wobble = math.sin(elapsed * 0.55 + net.phase) * net.drift
            jitter = random.uniform(-1.1, 1.1)
            rssi = int(round(max(-92, min(-28, net.base_rssi + wobble + jitter))))
            aps.append(
                AccessPoint(
                    bssid=net.bssid,
                    ssid=net.ssid,
                    channel=net.channel,
                    frequency_mhz=channels.channel_to_freq(net.band, net.channel),
                    width_mhz=net.width,
                    rssi=rssi,
                    security=net.security,
                    vendor=net.vendor,
                    phy=net.phy,
                    first_seen=self._started,
                    last_seen=now,
                    source="demo",
                )
            )
        duration = (time.perf_counter() - started) * 1000.0 + random.uniform(28, 90)
        return ScanOutcome(
            aps=aps,
            duration_ms=duration,
            adapter=self.list_adapters()[0],
            warnings=["Demo mode: values are simulated."],
        )
