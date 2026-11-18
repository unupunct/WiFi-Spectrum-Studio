"""Windows backend: netsh wlan (real observations, no simulated data)."""

from __future__ import annotations

import logging
import re
import time

from ...core import channels
from ...core.models import AccessPoint, AdapterInfo, Band
from .base import (
    NoAdapterError,
    ScanBackend,
    ScanError,
    ScanOutcome,
    run_command,
    vendor_for,
)

log = logging.getLogger(__name__)

_FIELD = re.compile(r"^\s{2,}([A-Za-z][A-Za-z0-9 ()./&#+_-]*?)\s*:\s*(.*)$")


def _fields(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = _FIELD.match(line)
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def _percent_to_dbm(pct: int) -> int:
    # Windows reports a 0-100% quality value; the widely used mapping is
    # dBm = (pct / 2) - 100. It is an estimate, and labelled as such in docs.
    return int(round(max(0, min(100, pct)) / 2.0 - 100))


def _parse_security(text: str) -> str:
    lowered = text.lower()
    if not text or "open" in lowered:
        return "Open"
    if "wpa3" in lowered:
        return "WPA3" if "enterprise" not in lowered else "WPA3-Ent"
    if "wpa2" in lowered:
        return "WPA2" if "enterprise" not in lowered else "WPA2-Ent"
    if "wpa" in lowered:
        return "WPA"
    if "wep" in lowered:
        return "WEP"
    return text


class WindowsBackend(ScanBackend):
    name = "windows"
    label = "Windows WLAN (netsh)"

    def available(self) -> tuple[bool, str]:
        try:
            out = run_command(["netsh", "wlan", "show", "interfaces"], timeout=8)
        except ScanError as exc:
            return False, str(exc)
        if re.search(r"^\s*Name\s*:", out, re.MULTILINE):
            return True, ""
        return False, "Wireless AutoConfig service is not available."

    def list_adapters(self) -> list[AdapterInfo]:
        try:
            interfaces = run_command(["netsh", "wlan", "show", "interfaces"], timeout=8)
        except ScanError as exc:
            raise NoAdapterError(str(exc)) from exc

        drivers = ""
        try:
            drivers = run_command(["netsh", "wlan", "show", "drivers"], timeout=8)
        except ScanError:
            pass

        adapters: list[AdapterInfo] = []
        blocks = re.split(r"\n(?=\s*Name\s*:)", interfaces)
        for block in blocks:
            values = _fields(block)
            name = values.get("Name", "").strip()
            if not name:
                continue
            description = values.get("Description", name)
            radio = values.get("Radio type", "")
            driver_block = self._driver_block(drivers, name)

            bands: list[Band] = []
            radio_lower = radio.lower()
            if any(x in radio_lower for x in ("802.11b", "802.11g", "802.11n", "802.11ax", "802.11be")):
                bands.append(Band.GHZ_24)
            if any(x in radio_lower for x in ("802.11a", "802.11ac", "802.11ax", "802.11be")):
                bands.append(Band.GHZ_5)
            if "6 ghz" in (driver_block + radio).lower() or "802.11be" in radio_lower:
                bands.append(Band.GHZ_6)
            if not bands:
                bands = [Band.GHZ_24]

            widths = [20]
            if "802.11n" in driver_block or "802.11ax" in driver_block:
                widths.append(40)
            if "802.11ac" in driver_block or "802.11ax" in driver_block:
                widths.append(80)
            if "802.11ax" in driver_block or "802.11be" in driver_block:
                widths.append(160)
            if "802.11be" in driver_block:
                widths.append(320)

            notes = [
                "Windows reports signal as a 0-100% quality value; dBm values are derived "
                "with the standard (pct/2)-100 mapping and are estimates.",
                "Channel width is not exposed by netsh; scans assume a 20 MHz primary channel.",
            ]
            adapters.append(
                AdapterInfo(
                    interface=name,
                    name=description,
                    vendor=driver_block.get("Provider", "") or self._vendor_from_name(description),
                    chipset=driver_block.get("Driver", description),
                    driver=driver_block.get("Driver", "Unknown"),
                    driver_version=driver_block.get("Version", "Unknown"),
                    bands=bands,
                    widths=sorted(set(widths)),
                    channels={},
                    supports_fft=False,
                    monitor_capable=False,
                    backend="netsh",
                    notes=notes,
                    is_demo=False,
                )
            )
        if not adapters:
            raise NoAdapterError("No wireless adapter was reported by netsh.")
        return adapters

    def _driver_block(self, text: str, iface_name: str) -> dict[str, str]:
        if not text:
            return {}
        blocks = re.split(r"\n(?=\s*Interface name\s*:)", text)
        for block in blocks:
            values = _fields(block)
            if values.get("Interface name", "").strip() == iface_name:
                return values
        return {}

    @staticmethod
    def _vendor_from_name(name: str) -> str:
        for vendor in ("Intel", "Qualcomm", "Realtek", "Broadcom", "MediaTek", "Killer", "Ralink", "Atheros"):
            if vendor.lower() in name.lower():
                return vendor
        return "Unknown"

    def capabilities(self, interface: str) -> AdapterInfo | None:
        for adapter in self.list_adapters():
            if adapter.interface == interface:
                return adapter
        return None

    def scan(self, interface: str | None) -> ScanOutcome:
        started = time.perf_counter()
        try:
            out = run_command(["netsh", "wlan", "show", "networks", "mode=bssid"], timeout=30)
        except ScanError as exc:
            raise ScanError(f"Windows wireless scan failed: {exc}") from exc

        if "SSID" not in out:
            raise ScanError(
                "Windows returned no WLAN data. Check that the WLAN AutoConfig service is "
                "running and that an adapter is enabled."
            )

        aps: dict[str, AccessPoint] = {}
        now = time.time()
        ssid = ""
        security = "Open"
        radio = ""
        band_hint: Band | None = None
        current: dict[str, str] = {}

        def flush() -> None:
            nonlocal current
            bssid = current.get("BSSID", "").lower()
            if not re.match(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$", bssid):
                current = {}
                return
            try:
                pct = int(re.sub(r"[^\d]", "", current.get("Signal", "0")) or 0)
            except ValueError:
                pct = 0
            rssi = _percent_to_dbm(pct)
            try:
                channel = int(re.sub(r"[^\d]", "", current.get("Channel", "0")) or 0)
            except ValueError:
                channel = 0
            band = self._resolve_band(band_hint, channel)
            freq = channels.channel_to_freq(band, channel)
            if not freq:
                current = {}
                return
            width = 20
            aps[bssid] = AccessPoint(
                bssid=bssid,
                ssid=ssid,
                channel=channel,
                frequency_mhz=freq,
                width_mhz=width,
                rssi=rssi,
                security=_parse_security(security),
                vendor=vendor_for(bssid),
                phy=radio or "802.11",
                first_seen=now,
                last_seen=now,
                hidden=not ssid,
                source="netsh",
            )
            current = {}

        for raw_line in out.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("SSID ") and ":" in line:
                flush()
                ssid = line.split(":", 1)[1].strip()
                security = "Open"
                band_hint = None
                continue
            if line.startswith("Authentication") and ":" in line:
                security = line.split(":", 1)[1].strip()
                continue
            if line.startswith("Radio type") and ":" in line:
                radio = line.split(":", 1)[1].strip()
                continue
            if line.startswith("Band") and ":" in line:
                value = line.split(":", 1)[1].strip().lower()
                if value.startswith("2"):
                    band_hint = Band.GHZ_24
                elif value.startswith("5"):
                    band_hint = Band.GHZ_5
                elif value.startswith("6"):
                    band_hint = Band.GHZ_6
                continue
            if line.startswith("BSSID") and ":" in line:
                flush()
                value = line.split(":", 1)[1].strip()
                current = {"BSSID": value}
                continue
            if current and ":" in line:
                key, _, value = line.partition(":")
                current[key.strip()] = value.strip()
        flush()

        if not aps:
            raise ScanError(
                "No networks were detected. Move closer to an access point or confirm that "
                "wireless scanning is permitted for this adapter."
            )

        duration = (time.perf_counter() - started) * 1000.0
        adapter = None
        if interface:
            try:
                adapter = self.capabilities(interface)
            except ScanError:
                adapter = None
        return ScanOutcome(aps=list(aps.values()), duration_ms=duration, adapter=adapter)

    @staticmethod
    def _resolve_band(hint: Band | None, channel: int) -> Band:
        if hint is not None:
            return hint
        if 0 < channel <= 14:
            return Band.GHZ_24
        if channel > 177:
            return Band.GHZ_6
        return Band.GHZ_5
