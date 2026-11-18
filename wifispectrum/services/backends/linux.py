"""Linux backend: iw (nl80211) primary, NetworkManager/nmcli fallback."""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

from ...core import channels
from ...core.models import AccessPoint, AdapterInfo, Band
from .base import (
    NoAdapterError,
    PermissionDeniedError,
    ScanBackend,
    ScanError,
    ScanOutcome,
    UnsupportedError,
    run_command,
    vendor_for,
)

log = logging.getLogger(__name__)


def _parse_width(block: str) -> int:
    m = re.search(r"channel width:\s*\d+\s*\((\d+)\s*MHz\)", block)
    if m:
        return int(m.group(1))
    if re.search(r"secondary channel offset:\s*(above|below)", block):
        return 40
    if "VHT160" in block:
        return 160
    return 20


def _parse_security(block: str) -> str:
    if "Authentication suites: SAE" in block or "Authentication suites: OWE" in block:
        if "PSK" in block and "SAE" in block:
            return "WPA2/WPA3"
        return "WPA3" if "SAE" in block else "OWE"
    if "RSN:" in block:
        if "802.1X" in block:
            return "WPA2-Ent"
        return "WPA2"
    if re.search(r"\n\tWPA:", block) or "WPA:" in block:
        return "WPA"
    if re.search(r"capability:.*Privacy", block) or "Privacy" in block:
        return "WEP"
    return "Open"


def _parse_scan(text: str) -> list[AccessPoint]:
    aps: dict[str, AccessPoint] = {}
    chunks = re.split(r"^BSS ", text, flags=re.MULTILINE)[1:]
    now = time.time()
    for chunk in chunks:
        header, _, body = chunk.partition("\n")
        bssid = header.split("(")[0].strip().lower()
        if not re.match(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$", bssid):
            continue

        freq_m = re.search(r"^[ \t]*freq:\s*(\d+)", body, re.MULTILINE)
        signal_m = re.search(r"^[ \t]*signal:\s*(-?[\d.]+)\s*dBm", body, re.MULTILINE)
        if not freq_m or not signal_m:
            continue
        freq = int(freq_m.group(1))
        rssi = int(round(float(signal_m.group(1))))

        ssid_m = re.search(r"^[ \t]*SSID:[ \t]?(.*)$", body, re.MULTILINE)
        ssid = ssid_m.group(1).strip() if ssid_m else ""
        if ssid.startswith("\x00") or not ssid:
            ssid = ""

        band = Band.from_frequency(freq)

        channel = 0
        primary_m = re.search(r"primary channel:\s*(\d+)", body)
        ds_m = re.search(r"DS Parameter set:\s*channel\s*(\d+)", body)
        if band is Band.GHZ_24 and ds_m:
            channel = int(ds_m.group(1))
        elif primary_m:
            channel = int(primary_m.group(1))
        elif ds_m:
            channel = int(ds_m.group(1))
        if not channel:
            channel = channels.freq_to_channel(freq)

        width = _parse_width(body)
        security = _parse_security(body)

        phy_m = re.search(r"^[ \t]*PHY:\s*(.+)$", body, re.MULTILINE)
        phy = phy_m.group(1).strip() if phy_m else ""
        if not phy:
            for token, label in (("EHT", "802.11be"), ("HE", "802.11ax"), ("VHT", "802.11ac"), ("HT", "802.11n")):
                if re.search(rf"\b{token}\b", body):
                    phy = label
                    break

        ap = AccessPoint(
            bssid=bssid,
            ssid=ssid,
            channel=channel,
            frequency_mhz=freq,
            width_mhz=width,
            rssi=rssi,
            security=security,
            vendor=vendor_for(bssid),
            phy=phy or "802.11",
            first_seen=now,
            last_seen=now,
            hidden=not ssid,
            source="iw",
        )
        existing = aps.get(bssid)
        if existing and existing.rssi >= ap.rssi:
            continue
        aps[bssid] = ap
    return list(aps.values())


def _split_nmcli(line: str) -> list[str]:
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def _parse_nmcli(text: str) -> list[AccessPoint]:
    aps: dict[str, AccessPoint] = {}
    now = time.time()
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = _split_nmcli(line)
        if len(parts) < 5:
            continue
        bssid = parts[0].strip().lower()
        if not re.match(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$", bssid):
            continue
        ssid = parts[1].strip()
        chan_field = parts[2].strip()
        freq_field = parts[3].strip()
        signal_field = parts[4].strip()
        security = parts[5].strip() if len(parts) > 5 else ""

        freq_m = re.search(r"(\d{4,5})", freq_field)
        freq = int(freq_m.group(1)) if freq_m else 0
        chan_m = re.match(r"^(\d+)", chan_field)
        channel = int(chan_m.group(1)) if chan_m else 0
        if not freq and channel:
            freq = channels.channel_to_freq(Band.from_frequency(2400 + channel * 5), channel)
        if not freq:
            continue
        if not channel:
            channel = channels.freq_to_channel(freq)

        try:
            pct = int(re.match(r"^(\d+)", signal_field).group(1))
            rssi = int(round(pct / 2.0 - 100))
        except (AttributeError, ValueError):
            rssi = -100

        sec = "Open"
        if "WPA3" in security and "WPA2" in security:
            sec = "WPA2/WPA3"
        elif "WPA3" in security:
            sec = "WPA3"
        elif "WPA2" in security:
            sec = "WPA2-Ent" if "802.1X" in security else "WPA2"
        elif "WPA" in security:
            sec = "WPA"
        elif "WEP" in security:
            sec = "WEP"

        aps[bssid] = AccessPoint(
            bssid=bssid,
            ssid=ssid,
            channel=channel,
            frequency_mhz=freq,
            width_mhz=20,
            rssi=rssi,
            security=sec,
            vendor=vendor_for(bssid),
            phy="802.11",
            first_seen=now,
            last_seen=now,
            hidden=not ssid,
            source="nmcli",
        )
    return list(aps.values())


class LinuxBackend(ScanBackend):
    name = "linux"
    label = "Linux nl80211 (iw / NetworkManager)"

    def __init__(self) -> None:
        self._iw_ok = True
        self._ifaces: list[AdapterInfo] = []
        self._phy_cache: dict[str, str] = {}

    # -- availability ------------------------------------------------------
    def available(self) -> tuple[bool, str]:
        if not Path("/sys/class/net").exists():
            return False, "No Linux network subsystem detected."
        if self._interfaces_from_iw() or self._interfaces_from_nmcli():
            return True, ""
        return False, "No wireless interfaces found (iw / nmcli)."

    def _run_iw(self, args: list[str]) -> str:
        return run_command(["iw", *args])

    def _interfaces_from_iw(self) -> list[str]:
        try:
            out = self._run_iw(["dev"])
        except ScanError:
            self._iw_ok = False
            return []
        found = []
        for match in re.finditer(r"Interface\s+(\S+).*?(?:\n\s+type\s+(\w+))?", out, re.DOTALL):
            iface = match.group(1)
            if iface.startswith("p2p"):
                continue
            found.append(iface)
        return found

    def _interfaces_from_nmcli(self) -> list[str]:
        try:
            out = run_command(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
        except ScanError:
            return []
        found = []
        for line in out.splitlines():
            parts = _split_nmcli(line)
            if len(parts) >= 2 and parts[1].strip() == "wifi":
                found.append(parts[0].strip())
        return found

    # -- adapter discovery -------------------------------------------------
    def list_adapters(self) -> list[AdapterInfo]:
        ifaces = self._interfaces_from_iw() or self._interfaces_from_nmcli()
        adapters: list[AdapterInfo] = []
        for iface in ifaces:
            info = self._build_adapter(iface)
            if info:
                adapters.append(info)
        self._ifaces = adapters
        return adapters

    def _sysfs(self, iface: str, leaf: str) -> str:
        try:
            return Path(f"/sys/class/net/{iface}/device/{leaf}").read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            return ""

    def _build_adapter(self, iface: str) -> AdapterInfo | None:
        if not Path(f"/sys/class/net/{iface}").exists():
            return None

        driver = ""
        driver_link = Path(f"/sys/class/net/{iface}/device/driver")
        try:
            driver = os.path.basename(os.readlink(driver_link))
        except OSError:
            pass

        version = ""
        bus_info = ""
        try:
            out = run_command(["ethtool", "-i", iface], timeout=6)
            for line in out.splitlines():
                key, _, value = line.partition(":")
                if key.strip() == "driver":
                    driver = driver or value.strip()
                elif key.strip() == "version":
                    version = value.strip()
                elif key.strip() == "bus-info":
                    bus_info = value.strip()
        except ScanError:
            pass

        model = ""
        if bus_info:
            try:
                out = run_command(["lspci", "-s", bus_info], timeout=4)
                line = out.strip().splitlines()[0] if out.strip() else ""
                if ":" in line:
                    model = line.split(":", 1)[1].strip()
                    model = re.sub(r"\[[0-9a-fA-F]{4}\]", "", model).strip()
            except (ScanError, IndexError):
                pass

        bands, widths, chan_map, monitor_ok = self._phy_capabilities(iface)
        if not bands:
            bands = [Band.GHZ_24, Band.GHZ_5]
            widths = [20, 40, 80]
        if not widths:
            widths = [20, 40]

        notes: list[str] = []
        if not chan_map:
            chan_map = {band.key: channels.band_channels(band) for band in bands}
        notes.append(
            "Standard Wi-Fi adapters report scanned BSS data, not continuous RF power. "
            "Spectrum curves are channel-shaped visualisations of real observations."
        )
        if not monitor_ok:
            notes.append("Monitor mode was not confirmed for this interface.")

        return AdapterInfo(
            interface=iface,
            name=model or driver.replace("_", " ").title() or iface,
            vendor=(model.split()[0] if model else "Unknown"),
            chipset=driver or "Unknown",
            driver=driver or "Unknown",
            driver_version=version or "Unknown",
            bands=bands,
            widths=widths,
            channels=chan_map,
            supports_fft=False,
            monitor_capable=monitor_ok,
            backend="iw/nl80211",
            notes=notes,
            is_demo=False,
        )

    def _phy_capabilities(self, iface: str) -> tuple[list[Band], list[int], dict[str, list[int]], bool]:
        phy = ""
        try:
            link = Path(f"/sys/class/net/{iface}/phy80211")
            phy = "phy" + os.path.basename(os.readlink(link)).replace("phy", "")
        except OSError:
            pass

        if not phy:
            try:
                out = self._run_iw(["dev", iface, "info"])
                m = re.search(r"wiphy\s+(\d+)", out)
                if m:
                    phy = f"phy{m.group(1)}"
            except ScanError:
                pass

        if not phy:
            return [], [], {}, False

        try:
            info = self._run_iw([phy, "info"])
        except ScanError:
            return [], [], {}, False

        bands: list[Band] = []
        chan_map: dict[str, list[int]] = {}
        current: Band | None = None
        for line in info.splitlines():
            if line.startswith("Band "):
                current = None
            freq_match = re.match(r"\s*\*\s*(\d{4,5})\s*MHz\s*\[(\d+)\]", line)
            if freq_match and current is None:
                freq = int(freq_match.group(1))
                band = Band.from_frequency(freq)
                current = band
                if band not in bands:
                    bands.append(band)
                chan_map.setdefault(band.key, []).append(int(freq_match.group(2)))
            elif freq_match and current is not None:
                freq = int(freq_match.group(1))
                band = Band.from_frequency(freq)
                if band is not current:
                    current = band
                    if band not in bands:
                        bands.append(band)
                chan_map.setdefault(band.key, []).append(int(freq_match.group(2)))

        widths: list[int] = [20, 40]
        if "VHT80" in info or "VHT Capabilities" in info:
            widths.append(80)
        if "VHT160" in info or "160 MHz" in info:
            widths.append(160)
        if "EHT" in info:
            widths.append(320)
        monitor_ok = "monitor" in info.lower()

        for band in bands:
            chan_map[band.key] = sorted(set(chan_map.get(band.key, [])))
        return bands, sorted(set(widths)), chan_map, monitor_ok

    def capabilities(self, interface: str) -> AdapterInfo | None:
        return self._build_adapter(interface)

    # -- scanning ----------------------------------------------------------
    def scan(self, interface: str | None) -> ScanOutcome:
        ifaces = [interface] if interface else (self._interfaces_from_iw() or self._interfaces_from_nmcli())
        if not ifaces:
            raise NoAdapterError("No wireless adapter is available for scanning.")

        warnings: list[str] = []
        last_error: Exception | None = None
        for iface in ifaces:
            started = time.perf_counter()
            if self._iw_ok:
                try:
                    out = self._run_iw(["dev", iface, "scan"])
                    aps = _parse_scan(out)
                    return ScanOutcome(
                        aps=aps,
                        duration_ms=(time.perf_counter() - started) * 1000.0,
                        adapter=self.capabilities(iface),
                        warnings=warnings,
                    )
                except PermissionDeniedError as exc:
                    warnings.append(f"iw: {exc}")
                    last_error = exc
                except ScanError as exc:
                    warnings.append(f"iw: {exc}")
                    last_error = exc

            try:
                out = run_command(
                    [
                        "nmcli", "-t", "-f",
                        "BSSID,SSID,CHAN,FREQ,SIGNAL,SECURITY",
                        "device", "wifi", "list", "--rescan", "yes",
                    ],
                    timeout=30,
                )
                aps = _parse_nmcli(out)
                return ScanOutcome(
                    aps=aps,
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                    adapter=self.capabilities(iface),
                    warnings=warnings + ["Results via NetworkManager (nmcli); channel width is reported as 20 MHz."],
                )
            except ScanError as exc:
                warnings.append(f"nmcli: {exc}")
                last_error = exc

        if isinstance(last_error, PermissionDeniedError):
            raise last_error
        if warnings:
            raise ScanError("Wireless scan failed. " + " | ".join(warnings[-3:]))
        raise UnsupportedError("No supported wireless scanning tool is available (iw or nmcli).")
