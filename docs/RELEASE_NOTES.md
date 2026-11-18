# WiFi Spectrum Studio 1.0.0

**WiFi Spectrum Studio** is a professional desktop application for analysing Wi-Fi
environments: live channel occupancy, spectrum waterfalls, channel interference
scoring and signal monitoring — with full data provenance and honest labelling.

Built with Python 3.12+, PySide6 and pyqtgraph. On Linux it reads real scans via
`iw` and NetworkManager (`nmcli` fallback); on Windows via `netsh wlan`. True FFT
traces are possible through an optional SoapySDR device; without one, Wi-Fi curves
are channel-shaped visualisations derived from scan observations and clearly
labelled as such.

## Highlights of this release

- **Live Spectrum** (default landing page): five metric cards, 2.4/5/6 GHz band tabs,
  channel-shaped spectrum curves, waterfall timeline, channel distribution chart,
  top detected networks and generated spectrum insights.
- **Channel Analyzer**: relative overlap scoring per channel (1.00 = busiest), quietest
  channel recommendation with confidence, alternatives and full insight list.
- **Network Discovery**: searchable/sortable network table with signal bars, BSSID,
  vendor, band and security columns; inspection drawer with signal tracking.
- **Signal Monitor**: per-network RSSI history charts, current/average/min/max/stability,
  CSV export.
- **Frequency Explorer**: channel map across 2.4/5/6 GHz with band summary and observed
  frequency table.
- **History & Reports**: SQLite scan history, per-scan detail, HTML/CSV/JSON/PDF exports.
- **Hardware**: adapter detection, SDR/FFT probe, diagnostics.

## Data honesty

Wi-Fi curves and waterfalls are channel-shaped visualisations derived from scan data
(channel, width, RSSI) — they are not FFT power measurements. True FFT requires a
supported SoapySDR device. Demonstration mode is clearly labelled in the UI and in every
export.

## Screenshots

| Page | Asset |
| --- | --- |
| Live Spectrum | `artifacts/spectrum.png` |
| Dashboard | `artifacts/dashboard.png` |
| Channel Analyzer | `artifacts/analyzer.png` |
| Network Discovery | `artifacts/discovery.png` |
| Signal Monitor | `artifacts/signal.png` |
| Frequency Explorer | `artifacts/frequency.png` |
| History & Reports | `artifacts/history.png` |
| Hardware | `artifacts/hardware.png` |
| Settings | `artifacts/settings.png` |

The Live Spectrum captures the design signature: metric cards, band tabs, spectrum
curves, waterfall, channel distribution, detected networks and insights in one view.

## Debian and Ubuntu

- Debian/Ubuntu: install from source (Python 3.12+, PySide6, pyqtgraph, numpy, `iw`, NetworkManager)
  or build the package with `bash packaging/build_deb.sh` on a Debian/Ubuntu host, then
  `sudo dpkg -i dist/wifispectrum_1.0.0_all.deb`.
- Or use the source release archive attached to this release (`wifispectrum-1.0.0.tar.gz`).

## Windows

- Release binary: `WiFiSpectrumStudio Setup v1.0.0.exe`.
- Requires Python-free operation; all Qt bindings bundled by the build.

## Usage

```bash
python run.py            # from the repository checkout
# or, after installing the release binary / Debian package
wifispectrum
```

Set **Settings → Demonstration mode** when no wireless adapter is available.
