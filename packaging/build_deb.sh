#!/usr/bin/env bash
# Build a Debian package for WiFi Spectrum Studio.
#
#   bash packaging/build_deb.sh
#
# Produces dist/wifispectrum_<version>_all.deb. Requires dpkg-deb.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(
  python3 -c "import re,pathlib; \
text = pathlib.Path('wifispectrum/core/constants.py').read_text(); \
print(re.search(r'APP_VERSION\s*=\s*[\"\\']([^\"\\']+)', text).group(1))"
)"
ARCH="all"
PKG="wifispectrum"
STAGE="$ROOT/build/${PKG}_${VERSION}_${ARCH}"
OUT="$ROOT/dist/${PKG}_${VERSION}_${ARCH}.deb"

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "error: dpkg-deb not found (install dpkg-dev)" >&2
  exit 1
fi

rm -rf "$ROOT/build" "$OUT"
mkdir -p \
  "$STAGE/DEBIAN" \
  "$STAGE/usr/lib/$PKG" \
  "$STAGE/usr/bin" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/scalable/apps"

# Application payload
cp -r "$ROOT/wifispectrum" "$STAGE/usr/lib/$PKG/"
cp "$ROOT/run.py" "$STAGE/usr/lib/$PKG/"
cp "$ROOT/requirements.txt" "$STAGE/usr/lib/$PKG/"
if [ -d "$ROOT/assets" ]; then
  cp -r "$ROOT/assets" "$STAGE/usr/lib/$PKG/"
fi
find "$STAGE/usr/lib" -name '__pycache__' -type d -prune -exec rm -rf {} +

# Launcher
cat > "$STAGE/usr/bin/$PKG" <<EOF
#!/bin/sh
exec python3 /usr/lib/$PKG/run.py "\$@"
EOF
chmod 0755 "$STAGE/usr/bin/$PKG"

# Desktop entry and icon
install -m 0644 "$ROOT/packaging/wifispectrum.desktop" \
  "$STAGE/usr/share/applications/wifispectrum.desktop"
install -m 0644 "$ROOT/assets/wifispectrum.svg" \
  "$STAGE/usr/share/icons/hicolor/scalable/apps/wifispectrum.svg"

# Control file with the real version and installed size
SIZE_KB="$(du -sk "$STAGE" | cut -f1)"
sed -e "s/@VERSION@/$VERSION/" \
    -e "s/@ARCH@/$ARCH/" \
    -e "s/@SIZE@/$SIZE_KB/" \
    "$ROOT/packaging/debian/control" > "$STAGE/DEBIAN/control"

dpkg-deb --build --root-owner-group "$STAGE" "$OUT"
echo "built $OUT"
