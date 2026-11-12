#!/usr/bin/env bash
set -Eeuo pipefail

GLOW_MATERIAL_COMMIT="8c98cd6bc787997e21fbd1692c608e1e066ad132"
GLOW_MATERIAL_URL="https://github.com/AxonShell/KDE-Glow-Material/archive/${GLOW_MATERIAL_COMMIT}.tar.gz"
WORK_DIR="${TMPDIR:-/tmp}/mulios-glow-material"
AIROOTFS="${MULIOS_AIROOTFS:-profile/airootfs}"

if [[ ! -d "$AIROOTFS" ]]; then
    echo "[ERROR]: airootfs directory not found: $AIROOTFS" >&2
    echo "[ERROR]: run this script from the MuliOS-Arch repository root." >&2
    exit 1
fi

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

echo "[INFO]: fetching Glow Material at ${GLOW_MATERIAL_COMMIT}"
curl -fsSL --retry 3 --retry-all-errors "$GLOW_MATERIAL_URL" -o "$WORK_DIR/glow-material.tar.gz"
tar -xzf "$WORK_DIR/glow-material.tar.gz" -C "$WORK_DIR"

SOURCE_ROOT="$(find "$WORK_DIR" -mindepth 1 -maxdepth 1 -type d -name 'KDE-Glow-Material-*' -print -quit)"
THEME_SOURCE="$SOURCE_ROOT/aurorae/glow-material"
for file in metadata.desktop glow-materialrc decoration.svg close.svg minimize.svg maximize.svg restore.svg; do
    [[ -f "$THEME_SOURCE/$file" ]] || {
        echo "[ERROR]: Glow Material package is missing $file" >&2
        exit 1
    }
done

install -d "$AIROOTFS/usr/share/aurorae/themes" "$AIROOTFS/etc/xdg" "$AIROOTFS/etc/skel/.config" "$AIROOTFS/etc/mulios"
rm -rf "$AIROOTFS/usr/share/aurorae/themes/glow-material"
cp -a "$THEME_SOURCE" "$AIROOTFS/usr/share/aurorae/themes/glow-material"

# Remove the previous third-party desktop theme from the generated image.
rm -rf \
    "$AIROOTFS/usr/share/plasma/desktoptheme/ROUNDED-DARK" \
    "$AIROOTFS/usr/share/plasma/look-and-feel/com.github.varlesh.rounded-dark" \
    "$AIROOTFS/usr/share/aurorae/themes/ROUNDED-DARK"
rm -f "$AIROOTFS/usr/share/color-schemes/ROUNDEDDARK.colors"

# Retire the custom QML greeter; use the maintained Breeze SDDM theme.
rm -rf "$AIROOTFS/usr/share/sddm/themes/mulios"

cat > "$AIROOTFS/etc/xdg/kdeglobals" <<'EOF'
[General]
ColorScheme=BreezeDark
Name=Breeze Dark

[KDE]
widgetStyle=Breeze

[Icons]
Theme=breeze-dark
EOF
cp "$AIROOTFS/etc/xdg/kdeglobals" "$AIROOTFS/etc/skel/.config/kdeglobals"

cat > "$AIROOTFS/etc/xdg/plasmarc" <<'EOF'
[Theme]
name=default
EOF
cp "$AIROOTFS/etc/xdg/plasmarc" "$AIROOTFS/etc/skel/.config/plasmarc"

cat > "$AIROOTFS/etc/xdg/kwinrc" <<'EOF'
[org.kde.kdecoration2]
library=org.kde.kwin.aurorae
theme=__aurorae__svg__glow-material

[Compositing]
AnimationSpeed=1
EOF
cp "$AIROOTFS/etc/xdg/kwinrc" "$AIROOTFS/etc/skel/.config/kwinrc"

cat > "$AIROOTFS/etc/sddm.conf" <<'EOF'
[Theme]
Current=breeze

[Users]
MinimumUid=1000
MaximumUid=60000
HideUsers=
HideShells=/usr/bin/nologin,/bin/nologin
RememberLastUser=true
RememberLastSession=true
EOF

printf 'glow\n' > "$AIROOTFS/etc/mulios/theme-variant"
echo "[INFO]: Glow Material Aurorae decoration installed; Breeze remains the Plasma shell and SDDM theme."
