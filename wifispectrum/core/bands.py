"""Frequency band enum (kept separate to avoid circular imports)."""

from __future__ import annotations

from enum import Enum


class Band(str, Enum):
    """Wireless frequency band. The value is the human label suffix."""

    GHZ_24 = "2.4"
    GHZ_5 = "5"
    GHZ_6 = "6"

    @property
    def label(self) -> str:
        return f"{self.value} GHz"

    @property
    def key(self) -> str:
        return self.value

    @property
    def short(self) -> str:
        return f"{self.value}G"

    @property
    def color(self) -> str:
        from .constants import BAND_COLORS

        return BAND_COLORS[self.value]

    @classmethod
    def all(cls) -> list["Band"]:
        return [cls.GHZ_24, cls.GHZ_5, cls.GHZ_6]

    @classmethod
    def from_frequency(cls, mhz: int) -> "Band":
        if 2400 <= mhz < 2500:
            return cls.GHZ_24
        if 5925 <= mhz < 7125:
            return cls.GHZ_6
        return cls.GHZ_5

    @classmethod
    def parse(cls, value: str | "Band" | None) -> "Band":
        if isinstance(value, Band):
            return value
        text = (value or "").strip().lower().replace("ghz", "").strip()
        return {
            "2.4": cls.GHZ_24,
            "2": cls.GHZ_24,
            "5": cls.GHZ_5,
            "6": cls.GHZ_6,
        }.get(text, cls.GHZ_24)
