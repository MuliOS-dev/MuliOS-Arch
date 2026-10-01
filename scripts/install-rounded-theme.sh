#!/usr/bin/env bash
set -Eeuo pipefail

THEME_COMMIT="157d8214499a5115a74d8e3f2a69f3d80cfbf113"
THEME_URL="https://github.com/varlesh/rounded/archive/${THEME_COMMIT}.tar.gz"
WORK_DIR="${TMPDIR:-/tmp}/mulios-rounded-theme"

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"

cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

echo "[INFO]: fetching ROUNDED KDE theme at ${THEME_COMMIT}"
curl -fsSL "$THEME_URL" -o "$WORK_DIR/rounded.tar.gz"
tar -xzf "$WORK_DIR/rounded.tar.gz" -C "$WORK_DIR"

THEME_ROOT="$WORK_DIR/rounded-${THEME_COMMIT}"

test -d "$THEME_ROOT/plasma/desktoptheme/ROUNDED-DARK"
test -d "$THEME_ROOT/plasma/look-and-feel/com.github.varlesh.rounded-dark"
test -d "$THEME_ROOT/aurorae/themes/ROUNDED-DARK"
test -f "$THEME_ROOT/plasma/desktoptheme/ROUNDED-DARK/colors"

install -d     profile/airootfs/usr/share/plasma/desktoptheme     profile/airootfs/usr/share/plasma/look-and-feel     profile/airootfs/usr/share/aurorae/themes     profile/airootfs/usr/share/color-schemes

rm -rf     profile/airootfs/usr/share/plasma/desktoptheme/ROUNDED-DARK     profile/airootfs/usr/share/plasma/look-and-feel/com.github.varlesh.rounded-dark     profile/airootfs/usr/share/aurorae/themes/ROUNDED-DARK

cp -a     "$THEME_ROOT/plasma/desktoptheme/ROUNDED-DARK"     profile/airootfs/usr/share/plasma/desktoptheme/

cp -a     "$THEME_ROOT/plasma/look-and-feel/com.github.varlesh.rounded-dark"     profile/airootfs/usr/share/plasma/look-and-feel/

cp -a     "$THEME_ROOT/aurorae/themes/ROUNDED-DARK"     profile/airootfs/usr/share/aurorae/themes/

install -m 0644     "$THEME_ROOT/plasma/desktoptheme/ROUNDED-DARK/colors"     profile/airootfs/usr/share/color-schemes/ROUNDEDDARK.colors

echo "[INFO]: ROUNDED KDE theme installed"
