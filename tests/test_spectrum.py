"""Channel-shaped spectrum curves (display geometry, not RF measurements)."""

from __future__ import annotations

import numpy as np

from wifispectrum.core.models import AccessPoint
from wifispectrum.services import spectrum_service


def make(rssi: int = -50, width: int = 20) -> AccessPoint:
    return AccessPoint(
        bssid="aa:bb:cc:dd:ee:ff",
        ssid="HomeNet",
        channel=6,
        frequency_mhz=2437,
        width_mhz=width,
        rssi=rssi,
    )


def test_shape_peaks_at_centre() -> None:
    xs = np.linspace(2400, 2480, 401)
    ys = spectrum_service.shape(xs, 2437, 20)
    peak_index = int(np.argmax(ys))
    assert abs(xs[peak_index] - 2437) < 0.5
    assert ys[peak_index] == 1.0
    assert ys[0] < 0.02 and ys[-1] < 0.02


def test_build_curve_matches_observed_rssi() -> None:
    curve = spectrum_service.build_curve(make(rssi=-47), "#00D9F5")
    assert curve.peak_y == -47
    assert curve.peak_x == 2437
    assert abs(float(np.max(curve.y)) - (-47)) < 0.1
    assert float(np.min(curve.y)) >= spectrum_service.GRAPH_FLOOR_DBM - 0.01


def test_assign_colors_is_stable() -> None:
    aps = [make(), AccessPoint(bssid="11:22:33:44:55:66", ssid="B", channel=1, frequency_mhz=2412)]
    first = spectrum_service.assign_colors(aps)
    second = spectrum_service.assign_colors(list(reversed(aps)))
    assert first == second
    assert set(first) == {ap.bssid for ap in aps}
