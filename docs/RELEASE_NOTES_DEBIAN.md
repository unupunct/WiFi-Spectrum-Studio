# WiFi Spectrum Studio 1.0.0 — Debian / Ubuntu

Source release for Debian and Ubuntu hosts.

## Install

```bash
git clone https://github.com/unupunct/WiFi-Spectrum-Studio.git
cd WiFi-Spectrum-Studio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## Debian package

On a Debian/Ubuntu host with build tooling:

```bash
bash packaging/build_deb.sh
sudo dpkg -i dist/wifispectrum_1.0.0_all.deb
sudo apt -f install
wifispectrum
```

Package contents: application at `/usr/lib/wifispectrum`, launcher at
`/usr/bin/wifispectrum`, desktop entry at `/usr/share/applications/wifispectrum.desktop`,
icon at `/usr/share/icons/hicolor/scalable/apps/wifispectrum.svg`.

## Debian/Ubuntu dependencies

```
python3, python3-venv, python3-pip, iw, network-manager,
python3-pyside6.qtwidgets, python3-pyqtgraph, python3-numpy
```

Optional: `python3-soapysdr` for true FFT traces.

## Permissions

Scanning typically needs `CAP_NET_ADMIN`/`CAP_NET_RAW` on `iw`, or NetworkManager
membership:

```bash
sudo setcap cap_net_admin,cap_net_raw+eip "$(command -v iw)"
```
