# Installation

WiFi Spectrum Studio runs on Linux (Parrot OS, Debian, Ubuntu, Kali) and
Windows. This guide covers installation, permissions, optional SDR support and
common problems.

## 1. Linux

### 1.1 Dependencies

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip \
    iw network-manager \
    python3-pyside6.qtwidgets python3-pyqtgraph python3-numpy
```

- `iw` is the preferred scan backend.
- NetworkManager (`nmcli`) is used automatically as a fallback when `iw` cannot
  scan (for example when the adapter is managed and busy).
- On distributions that package PySide6 as `python3-pyside6`, install the
  `qtwidgets` sub-package; if unsure, install PySide6 from PyPI in a virtual
  environment instead.

### 1.2 Install in a virtual environment (recommended)

```bash
git clone <repository> wifi-spectrum-studio
cd wifi-spectrum-studio
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python run.py
```

For a desktop entry during development, run `python run.py` from the project
directory or install the Debian package described below.

### 1.3 Permissions

Scanning with `iw dev <iface> scan` normally requires either root or the
`CAP_NET_ADMIN` / `CAP_NET_RAW` capability on the binary:

```bash
sudo setcap cap_net_admin,cap_net_raw+eip "$(command -v iw)"
```

Alternatively, `nmcli device wifi list` works for users in the `netdev` or
`network` group without elevating the whole application. If scanning fails, the
application automatically tries the fallback backend and reports the error in
the Hardware page and the status bar.

> Do not run the whole GUI as root. Prefer capabilities or `nmcli`.

### 1.4 Debian package

```bash
bash packaging/build_deb.sh
sudo dpkg -i dist/wifispectrum_1.0.0_all.deb
sudo apt -f install     # only if dependencies are missing
wifispectrum
```

The package places the application in `/usr/lib/wifispectrum`, the launcher in
`/usr/bin/wifispectrum`, and the menu entry in
`/usr/share/applications/wifispectrum.desktop`.

## 2. Windows

1. Install Python 3.12 or newer from python.org (tick **Add python.exe to PATH**).
2. Open PowerShell in the project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Windows scans use `netsh wlan show networks mode=bssid`. Notes:

- RSSI is derived from the reported signal percentage with `(pct / 2) - 100`;
  treat it as an estimate.
- Some channels and BSSIDs are only visible to the WLAN service when location
  permissions are enabled (Windows 11).
- `netsh` is slower than `iw`; choose a 3–5 second scan interval on Windows.

## 3. Optional: SDR and true FFT

True FFT traces require:

```bash
sudo apt install python3-soapysdr soapysdr-module-rtlsdr soapysdr-module-hackrf
# inside the virtual environment:
pip install soapysdr
```

Verify the device is visible:

```bash
SoapySDRUtil --info
```

The Hardware page reports whether SoapySDR bindings and a device are present.
Without a device, the FFT tab remains disabled and the application continues to
show channel-shaped Wi-Fi visualisations derived from scan data. Those curves
are **not** presented as measured RF power.

## 4. First run

1. Launch the application (`python run.py` or `wifispectrum`).
2. The Live Spectrum page opens by default.
3. If no adapter is detected, the app offers demonstration mode. Enable it in
   **Settings → Hardware & Demonstration** to explore the interface.
4. Press **Scan Now** (or wait for the automatic interval) to populate pages.
5. Check **Hardware → Diagnostics** for the log directory, data directory and
   the last backend error.

## 5. Data locations

| Item | Linux | Windows |
| --- | --- | --- |
| Settings | `~/.config/WiFiSpectrumStudio/settings.json` | `%APPDATA%\WiFiSpectrumStudio\settings.json` |
| Database | `~/.local/share/WiFiSpectrumStudio/history.db` | `%LOCALAPPDATA%\WiFiSpectrumStudio\history.db` |
| Logs | `~/.local/share/WiFiSpectrumStudio/logs` | `%LOCALAPPDATA%\WiFiSpectrumStudio\logs` |
| Exports | `~/Documents/WiFi Spectrum Studio` | `%USERPROFILE%\Documents\WiFi Spectrum Studio` |

All paths are shown on the Hardware page.

## 6. Troubleshooting

**“No wireless adapters were detected.”**
: Check `iw dev` and `nmcli device status`. On Linux, install `iw` and
  NetworkManager; on Windows confirm the WLAN service is running
  (`net start wlansvc`). Enable the adapter in the OS network settings.

**Scans return no networks.**
: The adapter may be disconnected or in a state where scanning is blocked. Try
  `sudo iw dev wlan0 scan | head` manually. If it works only as root, apply the
  capability described above. If `iw` fails, the `nmcli` fallback should still
  return results.

**Window is scaled strangely on Wayland.**
: Run with `QT_QPA_PLATFORM=xcb` if XWayland is available, or set
  `QT_SCALE_FACTOR=1`. Fractional scaling support depends on the Qt version.

**Fonts look wrong / boxes appear.**
: Install a common font family (`fonts-dejavu`, `fonts-inter`) or run on a
  desktop session with a font service. Offscreen screenshot rendering needs at
  least one system font installed.

**SDR tab stays disabled.**
: SoapySDR bindings are optional and must be installed in the same Python
  environment as the application. Check the reason shown on the Hardware page.

**Reports fail to write.**
: The export directory must exist and be writable. Change it in Settings; the
  application creates missing subdirectories but cannot create a directory it
  has no permission for.

**Resetting preferences.**
: Use **Settings → Reset defaults**, or delete `settings.json` while the
  application is closed. History is stored separately and is not removed by a
  settings reset.
