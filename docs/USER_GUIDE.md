# User guide

WiFi Spectrum Studio is organised as nine pages. The Live Spectrum page opens
by default; use the sidebar or `Ctrl+1` … `Ctrl+9` to move between pages.

The top bar always shows the monitoring state, the selected adapter, the active
band, the clock and — when applicable — a **DEMO DATA** marker. The bottom bar
shows scan progress, the last update time, the next scan countdown and the
current data source.

The interface is designed for 1600×900. On smaller windows the Live Spectrum
and Channel Analyzer pages keep their designed canvas and scroll instead of
squeezing labels or hiding controls; every other page reflows normally.

> **Data honesty.** Wi-Fi curves and waterfalls are channel-shaped
> visualisations built from scan results (channel, width, RSSI). They are not
> FFT power measurements. True FFT is available only when a SoapySDR device is
> installed and detected, and the interface is labelled accordingly.

---

## 1. Dashboard

A one-screen summary for a quick health check.

- **Metric cards** — networks observed, bands with traffic, strongest signal,
  2.4 GHz channel density and the number of stored scans.
- **Band Overview** — per band: access-point count, share of channels occupied
  and the busiest channels. Density is a comparison of used channels, not
  airtime.
- **Signal Distribution** — observed networks grouped into RSSI buckets.
- **Monitoring Health** — data source, adapter, interface, bands, interval, last
  scan duration, stored scans and SDR status.
- **Recent Activity** — the last completed scans with timestamps and durations.

Buttons: **Scan Now**, **Open Live Spectrum**, **View History**.

---

## 2. Live Spectrum

The signature workspace for the selected band.

- **Five metric cards** — access points in the band, active band and channel
  count, strongest signal, channels in use, and channel congestion.
- **Band tabs** — 2.4 / 5 / 6 GHz. A band with no adapter support is disabled.
- **Wi-Fi / FFT tabs** — Wi-Fi shows channel-shaped curves for observed
  networks. FFT is enabled only with a real SDR.
- **Spectrum graph** — each curve is centred on the AP's channel with a width
  derived from its channel width. Scroll to zoom, drag to pan, double-click to
  reset. Hover for a crosshair readout.
- **Waterfall** — one row per scan, coloured by the same observations. Play,
  pause, clear, zoom and palette controls are in the panel header.
- **Channel Distribution** — observed networks per channel; hover a bar for the
  exact count.
- **Detected Networks** — the five strongest networks in the band. **View All**
  opens Network Discovery.
- **Spectrum Insights** — generated observations (overlap, wide channels, strong
  and weak signals, alternative band suggestions).
- **Run Channel Analyzer** — opens the analyzer for the current band.

**Scan Now** triggers an immediate scan; **Pause** stops the background
monitor. The demo notice bar can be dismissed; it reappears on restart while
demo mode is enabled.

---

## 3. Channel Analyzer

Scores every channel in the selected band and recommends the quietest one.

- **Recommended Channel** — channel number, centre frequency, confidence
  (high/medium/low with a bar), the reasoning, and up to three alternatives.
- **Band Congestion** — density meter, busiest and quietest channel, number of
  overlapping pairs.
- **Interference Profile** — relative overlap per channel. **1.00 is the busiest
  channel in the band**, not an absolute airtime percentage. The recommended
  channel is outlined in cyan.
- **Channel Assessment** — table of channel, frequency, network count, index and
  a verdict (clear → severe overlap).
- **Analysis Insights** — the full generated list for this band, with
  supporting measurements.

**Export Report** writes the current analysis using the configured export
directory.

---

## 4. Network Discovery

Every access point from the latest scan.

- Search by SSID, BSSID or vendor.
- Filter by band (All / 2.4 / 5 / 6 GHz) and by security (All / Open / WPA2 /
  WPA3 …).
- Sort by strongest signal, channel, SSID or band.
- Columns: SSID, BSSID, vendor, signal (bars + dBm), channel, band, security.
- Click a row to open the inspection drawer: full radio details, channel span,
  first/last seen and the **Track signal** action.
- **Scan Now** requests a fresh scan; **Export CSV** saves the current table.

Observed values only: channel width and RSSI come directly from the backend.

---

## 5. Signal Monitor

Track how individual networks behave over time.

1. Pick a network from the dropdown (sorted by signal) and press **Track**.
   The strongest network is tracked automatically on first visit.
2. The chart plots RSSI over time. The dashed yellow line is the average.
3. Stat blocks show current, average, minimum, maximum, stability and sample
   count. Stability is the share of samples within 5 dB of the mean.
4. Remove a network with the small × button on its row.

Samples arrive once per scan and are kept in memory for the configured window
(default 30 minutes). **Export Log** writes a CSV for the tracked networks;
**Clear History** clears only the in-memory samples.

The chart fits the samples it has; a short session therefore shows a short time
axis rather than a long empty window.

---

## 6. Frequency Explorer

Shows how observed networks spread across the spectrum.

- **Channel Map** — one lane per band. Cells mark channels at their centre
  frequency; fill intensity reflects how many networks reported that channel.
  2.4 GHz channels are 5 MHz apart and drawn as narrow slots for legibility.
  Hover a cell for details.
- **Band Summary** — networks per band, channels in use, widest channel and
  average RSSI, with proportional bars.
- **Observed Frequencies** — every network sorted by centre frequency, with
  band, channel, frequency, width, RSSI and security. Filter by band with the
  segmented control.
- **Open Channel Analyzer** switches to the analyzer for deeper scoring.

Cells represent channel occupancy from scan data, not measured signal width.

---

## 7. History & Reports

Browse what the application has recorded.

- **Metric cards** — scans recorded, observations stored, database size and
  stored recommendations.
- **Recent Scans** — timestamp, band, network count, duration and source
  (hardware/demo). Selecting a row loads its networks in **Scan Detail**.
- **Scan Detail** — timestamp, networks, duration, adapter and a table of the
  captured networks. Click a network to inspect it.
- **Exports** — HTML (human-readable report), CSV (scan list), JSON (full data)
  and PDF (printable report). Files are written to the export directory and the
  resulting path is shown in a notice.
- **Clear History** — deletes stored scans and observations after confirmation.
  Settings and exported files are not affected.

Filters: last 24 hours / 7 days / 30 days / all (depending on availability in
your build). Empty states explain what will appear once scans are stored.

---

## 8. Hardware

What the application is actually using.

- **Wireless Adapters** — every detected adapter with interface, backend,
  bands, monitor-mode support and a demo marker. Select one to inspect it.
- **Adapter Details** — vendor, chipset, driver and version, supported bands,
  channel widths, monitor capability, FFT capability and data source.
- **SDR / True FFT** — SoapySDR availability, the reason it is unavailable, and
  detected devices. **Probe again** re-runs detection.
- **Diagnostics** — application version, platform, Python version, scan
  backend, last backend error, log and data directories. **Copy diagnostics**
  copies a support-friendly summary to the clipboard.
- **Refresh** re-detects adapters in the background.

If no adapter exists, the page explains how to install the Linux tooling or
enable demonstration mode.

---

## 9. Settings

Preferences apply immediately and are saved to the user configuration file
shown in the header.

| Group | Options |
| --- | --- |
| Scanning | Scan interval (1/2/3/5/10 s), start monitoring automatically, desktop notifications |
| Display | Waterfall palette (Spectrum, Inferno, Ice, Viridis, Amber), reduce motion, regulatory region (World, US, EU, JP) |
| History & Storage | Signal-history window, retention period, export directory (with browse) |
| Hardware & Demonstration | Demonstration mode, SDR/true FFT, preferred SDR device |

- **Region** changes which channels are considered valid by the analyzer and
  explorer. The adapter/driver remains authoritative for what can actually be
  scanned.
- **Demonstration mode** is labelled everywhere; turning it off returns to
  hardware scans.
- **SDR** controls are disabled when SoapySDR is unavailable, with the reason
  shown in the device field.
- **Reset defaults** restores every preference. Scans, history and exported
  files are not deleted.

---

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+1` … `Ctrl+9` | Jump to page 1–9 |
| `Ctrl+F` | Focus the search field (Network Discovery) |
| `Ctrl+R` / `F5` | Scan now |
| `Ctrl+,` | Open Settings |
| `Esc` | Close the inspection drawer |

## Export formats

| Format | Contents |
| --- | --- |
| HTML | Self-contained report with summary, per-band tables and insights |
| CSV | One row per observed network (scan list export) |
| JSON | Full snapshot including metadata and per-network fields |
| PDF | Printable version of the HTML report via Qt's PDF writer |

All exports include a timestamp and clearly mark demo data when it was
simulated.
