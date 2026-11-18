"""Scan backend contracts, shared command helpers and vendor lookup."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

from ...core.models import AccessPoint, AdapterInfo


class ScanError(RuntimeError):
    """Base error for anything that prevents a scan from completing."""


class NoAdapterError(ScanError):
    pass


class PermissionDeniedError(ScanError):
    pass


class UnsupportedError(ScanError):
    pass


@dataclass
class ScanOutcome:
    aps: list[AccessPoint]
    duration_ms: float
    adapter: AdapterInfo | None = None
    warnings: list[str] | None = None


OUI_VENDORS = {
    "000C29": "VMware",
    "001A11": "Google",
    "001B63": "Apple",
    "001C42": "Parallels",
    "001E58": "D-Link",
    "0022B0": "D-Link",
    "00248C": "ASUSTek",
    "0026F2": "NETGEAR",
    "002618": "ASUSTek",
    "005056": "VMware",
    "00A0C5": "Zyxel",
    "00E04C": "Realtek",
    "0418D6": "Ubiquiti",
    "04A151": "NETGEAR",
    "080027": "Oracle VirtualBox",
    "0C8063": "ASUSTek",
    "0CD502": "Intel",
    "101F74": "Hewlett Packard",
    "18E829": "Ubiquiti",
    "245A4C": "Ubiquiti",
    "24A43C": "Ubiquiti",
    "2C3033": "NETGEAR",
    "349971": "Huawei",
    "38D547": "ASUSTek",
    "3C5A37": "Samsung",
    "3C7C3F": "ASUSTek",
    "40B076": "ASUSTek",
    "44D9E7": "Ubiquiti",
    "48A6B8": "Sonos",
    "4C5E0C": "Cisco",
    "50C7BF": "TP-Link",
    "52544C": "Google",
    "544E90": "Apple",
    "58EF68": "Belkin",
    "5C3A45": "ASUSTek",
    "60A4D0": "Samsung",
    "641666": "MikroTik",
    "68D79A": "Ubiquiti",
    "6C5AB0": "Tp-Link",
    "70A741": "Ubiquiti",
    "74DA38": "Edimax",
    "78D6F0": "Samsung",
    "78E3B5": "Huawei",
    "7C8BCA": "Intel",
    "803F5D": "Wistron",
    "84D81B": "TP-Link",
    "8C882B": "Intel",
    "94B40F": "Aruba",
    "A0C9A0": "Murata",
    "A4C3F0": "Intel",
    "A85E45": "ASUSTek",
    "AC84C6": "TP-Link",
    "B0487A": "TP-Link",
    "B0BE76": "TP-Link",
    "B827EB": "Raspberry Pi",
    "C0EEFB": "Huawei",
    "C46E1F": "TP-Link",
    "C8D3A3": "D-Link",
    "D8F15B": "Espressif",
    "DC4EF4": "Shenzhen",
    "E0D55E": "GIGA-BYTE",
    "E4F365": "Intel",
    "EC086B": "TP-Link",
    "F01898": "Apple",
    "F09FC2": "Ubiquiti",
    "F4F26D": "TP-Link",
    "F8D111": "TP-Link",
    "FCECDA": "Ubiquiti",
    "FCE998": "Apple",
    "3462FA": "Intel",
    "3C2EFF": "Apple",
    "6038E0": "Belkin",
    "6C3B6B": "MikroTik",
    "B4FBE4": "Ubiquiti",
    "DCA632": "Raspberry Pi",
}


def vendor_for(bssid: str) -> str:
    prefix = re.sub(r"[^0-9A-Fa-f]", "", bssid).upper()[:6]
    return OUI_VENDORS.get(prefix, "Unknown")


def run_command(args: list[str], timeout: int = 25) -> str:
    """Run a command and return stdout, translating failures to ScanError."""
    if shutil.which(args[0]) is None:
        raise UnsupportedError(f"Required tool '{args[0]}' is not installed.")
    kwargs: dict = {
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(args, **kwargs)
    except FileNotFoundError as exc:
        raise UnsupportedError(f"Required tool '{args[0]}' is not installed.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ScanError(f"'{' '.join(args)}' timed out after {timeout}s.") from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        lowered = stderr.lower()
        if "permission denied" in lowered or "operation not permitted" in lowered:
            raise PermissionDeniedError(
                "Permission denied. Run the application with the permissions "
                "required for wireless scanning (sudo or the correct netdev capabilities)."
            )
        if "not found" in lowered or "no such device" in lowered:
            raise NoAdapterError(stderr or f"'{args[0]}' reported a missing device.")
        raise ScanError(stderr or f"'{' '.join(args)}' failed with code {proc.returncode}.")
    return proc.stdout


class ScanBackend:
    name = "base"
    label = "Base backend"
    is_demo = False

    def available(self) -> tuple[bool, str]:
        return True, ""

    def list_adapters(self) -> list[AdapterInfo]:
        raise NotImplementedError

    def scan(self, interface: str | None) -> ScanOutcome:
        raise NotImplementedError

    def capabilities(self, interface: str) -> AdapterInfo | None:
        return None
