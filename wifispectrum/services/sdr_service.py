"""Optional SDR integration (SoapySDR / GNU Radio).

True FFT spectrum is only offered when an SDR device and its Python bindings
are actually present. Nothing is simulated unless the user explicitly enables
the clearly-labelled simulated SDR source.
"""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass

import numpy as np

from ..core.models import Band

log = logging.getLogger(__name__)


@dataclass
class SDRDevice:
    driver: str
    label: str
    serial: str = ""
    hardware: str = ""
    sample_rate_range: tuple[float, float] = (0.0, 0.0)
    frequency_range: tuple[float, float] = (0.0, 0.0)


@dataclass
class FFTFrame:
    frequencies: np.ndarray
    power_db: np.ndarray
    center_freq: float
    sample_rate: float
    timestamp: float


class SDRService:
    def __init__(self):
        self._available: bool | None = None
        self._reason = ""
        self._devices: list[SDRDevice] = []
        self._sdr = None

    # -- probe -------------------------------------------------------------
    def probe(self) -> tuple[bool, str]:
        if self._available is not None:
            return self._available, self._reason
        if importlib.util.find_spec("SoapySDR") is None:
            self._available = False
            self._reason = (
                "SoapySDR Python bindings are not installed. Install python3-soapysdr and the "
                "vendor driver module to enable real FFT spectrum analysis."
            )
            return self._available, self._reason
        try:
            import SoapySDR  # type: ignore

            self._sdr = SoapySDR
            results = SoapySDR.Device.enumerate()
            self._devices = []
            for result in results:
                driver = str(result.get("driver", ""))
                label = str(result.get("label", driver or "SDR device"))
                self._devices.append(
                    SDRDevice(
                        driver=driver,
                        label=label,
                        serial=str(result.get("serial", "")),
                        hardware=str(result.get("hardware", "")),
                    )
                )
            if self._devices:
                self._available = True
                self._reason = f"{len(self._devices)} SDR device(s) detected via SoapySDR."
            else:
                self._available = False
                self._reason = "SoapySDR is installed but no compatible SDR device was found."
        except Exception as exc:  # noqa: BLE001 - vendor bindings raise broadly
            self._available = False
            self._reason = f"SoapySDR probe failed: {exc}"
        return self._available, self._reason

    @property
    def available(self) -> bool:
        ok, _ = self.probe()
        return ok

    @property
    def reason(self) -> str:
        self.probe()
        return self._reason

    @property
    def devices(self) -> list[SDRDevice]:
        self.probe()
        return list(self._devices)

    def gnuradio_available(self) -> bool:
        return importlib.util.find_spec("gnuradio") is not None

    # -- capture -----------------------------------------------------------
    def capture_fft(
        self,
        center_freq: float,
        sample_rate: float = 20e6,
        bins: int = 1024,
        gain: float | None = None,
        band: Band | None = None,
    ) -> FFTFrame | None:
        """Single FFT sweep. Returns ``None`` when no SDR is available."""
        if not self.available or self._sdr is None:
            return None
        SoapySDR = self._sdr
        try:
            device = SoapySDR.Device({"driver": self._devices[0].driver})
            device.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, sample_rate)
            if gain is not None:
                device.setGain(SoapySDR.SOAPY_SDR_RX, 0, gain)
            stream = device.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
            device.activateStream(stream)
            buffer = np.empty(bins, dtype=np.complex64)
            samples = np.zeros(bins, dtype=np.complex64)
            collected = 0
            for _ in range(8):
                status = device.readStream(stream, [buffer], len(buffer), timeoutUs=400000)
                if status.ret > 0:
                    chunk = buffer[: status.ret]
                    samples[collected : collected + chunk.size] = chunk[: bins - collected]
                    collected += chunk.size
                    if collected >= bins:
                        break
            device.deactivateStream(stream)
            device.closeStream(stream)
            if collected == 0:
                return None
            window = np.hanning(collected)
            spectrum = np.abs(np.fft.fftshift(np.fft.fft(samples[:collected] * window)))
            power = 20 * np.log10(np.maximum(spectrum, 1e-12)) - 60.0
            freqs = np.fft.fftshift(np.fft.fftfreq(collected, 1.0 / sample_rate)) + center_freq
            import time

            return FFTFrame(
                frequencies=freqs,
                power_db=power.astype(np.float32),
                center_freq=center_freq,
                sample_rate=sample_rate,
                timestamp=time.time(),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("SDR capture failed: %s", exc)
            self._reason = f"SDR capture failed: {exc}"
            return None
