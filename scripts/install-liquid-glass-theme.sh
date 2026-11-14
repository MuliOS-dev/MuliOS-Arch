#!/usr/bin/env bash
set -Eeuo pipefail

# Build-time staging installer for the KDE Plasma Liquid Glass setup.
# Upstream source: https://github.com/david-x3d/kde-plasma-liquid-glass-theme
LIQUID_GLASS_COMMIT="d90cf3e5467ff9cf75eb69d47663d86e8d8ea0fa"
LIQUID_GLASS_REPOSITORY="https://github.com/david-x3d/kde-plasma-liquid-glass-theme.git"
WORK_DIR="${TMPDIR:-/tmp}/mulios-liquid-glass-${UID}"
AIROOTFS="${MULIOS_AIROOTFS:-profile/airootfs}"
BUILD_ROOT="${WORK_DIR}/build"

if [[ ! -d "$AIROOTFS" ]]; then
    echo "[ERROR]: airootfs directory not found: $AIROOTFS" >&2
    echo "[ERROR]: run this script from the MuliOS-Arch repository root." >&2
    exit 1
fi

for command in git cmake; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "[ERROR]: required build tool not found: $command" >&2
        exit 1
    }
done

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR" "$BUILD_ROOT"
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

echo "[INFO]: fetching KDE Liquid Glass theme at ${LIQUID_GLASS_COMMIT}"
git clone --quiet --depth 1 --recurse-submodules --shallow-submodules \
    --branch main "$LIQUID_GLASS_REPOSITORY" "$WORK_DIR/source"
git -C "$WORK_DIR/source" checkout --quiet "$LIQUID_GLASS_COMMIT"
git -C "$WORK_DIR/source" submodule update --init --recursive --depth 1

SOURCE="$WORK_DIR/source"
LAYAN="$SOURCE/Layan-kde"
AIROOTFS="$(realpath "$AIROOTFS")"
USR="$AIROOTFS/usr"

for path in \
    "$LAYAN/plasma/desktoptheme/Layan" \
    "$LAYAN/plasma/desktoptheme/common" \
    "$LAYAN/plasma/look-and-feel/com.github.vinceliuice.Layan" \
    "$LAYAN/color-schemes/Layan.colors" \
    "$SOURCE/themes/modified-layan"; do
    [[ -e "$path" ]] || {
        echo "[ERROR]: Liquid Glass source is missing: $path" >&2
        exit 1
    }
done

echo "[INFO]: staging Layan Plasma theme and Liquid Glass overrides"
install -d \
    "$USR/share/plasma/desktoptheme/Layan" \
    "$USR/share/plasma/look-and-feel" \
    "$USR/share/color-schemes" \
    "$USR/share/icons" \
    "$USR/share/aurorae/themes" \
    "$AIROOTFS/etc/xdg" \
    "$AIROOTFS/etc/skel/.config" \
    "$AIROOTFS/etc/mulios"

cp -a "$LAYAN/plasma/desktoptheme/common" "$USR/share/plasma/desktoptheme/Layan/"
cp -a "$LAYAN/plasma/desktoptheme/Layan/." "$USR/share/plasma/desktoptheme/Layan/"
cp -a "$SOURCE/themes/modified-layan/." "$USR/share/plasma/desktoptheme/Layan/"
cp -a "$LAYAN/plasma/look-and-feel/com.github.vinceliuice.Layan" "$USR/share/plasma/look-and-feel/"
install -m 0644 "$LAYAN/color-schemes/Layan.colors" "$USR/share/color-schemes/Layan.colors"

# WhiteSur-dark is the icon theme paired with the upstream Liquid Glass setup.
bash "$SOURCE/WhiteSur-icon-theme/install.sh" \
    --dest "$USR/share/icons" --theme default --kde-plasma

build_component() {
    local name="$1"
    local source_dir="$2"
    local slug="$3"
    shift 3

    [[ -f "$source_dir/CMakeLists.txt" ]] || {
        echo "[ERROR]: $name source is unavailable: $source_dir" >&2
        exit 1
    }

    local build_dir="$BUILD_ROOT/$slug"
    echo "[INFO]: building $name"
    cmake -S "$source_dir" -B "$build_dir" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/usr \
        -DKDE_INSTALL_USE_QT_SYS_PATHS=ON \
        -DBUILD_TESTING=OFF \
        -Wno-dev "$@"
    cmake --build "$build_dir" --parallel
    DESTDIR="$AIROOTFS" cmake --install "$build_dir"
}

# Build the Qt/KWin components against the exact Plasma/KWin SDK in the build
# environment, then stage their install tree into the ISO root filesystem.
build_component "Darkly application style" "$SOURCE/Darkly" darkly \
    -DBUILD_QT5=OFF -DBUILD_QT6=ON
build_component "BreezeEnhanced window decoration" "$SOURCE/BreezeEnhanced" breezeenhanced
build_component "Better Blur DX" "$SOURCE/Better-Blur-DX" better-blur-dx
build_component "KDE Rounded Corners" "$SOURCE/KDE-Rounded-Corners" rounded-corners

# Retire the previous ROUNDED-DARK package from this image.
rm -rf \
    "$USR/share/plasma/desktoptheme/ROUNDED-DARK" \
    "$USR/share/plasma/look-and-feel/com.github.varlesh.rounded-dark" \
    "$USR/share/aurorae/themes/ROUNDED-DARK"
rm -f "$USR/share/color-schemes/ROUNDEDDARK.colors"

cat > "$AIROOTFS/etc/xdg/kdeglobals" <<'EOF'
[General]
ColorScheme=Layan
Name=Liquid Glass

[KDE]
widgetStyle=Darkly

[Icons]
Theme=WhiteSur-dark
EOF
cp "$AIROOTFS/etc/xdg/kdeglobals" "$AIROOTFS/etc/skel/.config/kdeglobals"

cat > "$AIROOTFS/etc/xdg/plasmarc" <<'EOF'
[Theme]
name=Layan
EOF
cp "$AIROOTFS/etc/xdg/plasmarc" "$AIROOTFS/etc/skel/.config/plasmarc"

cat > "$AIROOTFS/etc/xdg/kwinrc" <<'EOF'
[org.kde.kdecoration2]
library=org.kde.breezeenhanced
theme=BreezeEnhanced

[Plugins]
better_blur_dxEnabled=true
kwin4_effect_shapecornersEnabled=true

[Effect-better-blur-dx]
BlurStrength=20
NoiseStrength=3
Brightness=86
Saturation=135
Contrast=112
ForceContrastParams=true
CornerRadius=16
WindowClasses=plasmashell,org.kde.plasmashell,krunner,yakuake,vesktop,discord
BlurMatching=true
BlurNonMatching=false
BlurDecorations=true
BlurMenus=true
BlurDocks=true
RefractionStrength=8
RefractionMode=0
RefractionEdgeSize=20
RefractionCornerRadius=16
RefractionRGBFringing=1

[Round-Corners]
Size=14
InactiveCornerRadius=12
AnimationDuration=180
UseNativeDecorationShadows=true
ShadowSize=55
InactiveShadowSize=35
ActiveShadowAlpha=120
InactiveShadowAlpha=70
OutlineThickness=1
InactiveOutlineThickness=1
EOF
cp "$AIROOTFS/etc/xdg/kwinrc" "$AIROOTFS/etc/skel/.config/kwinrc"

printf 'liquid-glass\n' > "$AIROOTFS/etc/mulios/theme-variant"

# Confirm that all selected desktop components landed in the image.
for path in \
    "$USR/share/plasma/desktoptheme/Layan/metadata.json" \
    "$USR/share/plasma/look-and-feel/com.github.vinceliuice.Layan/metadata.json" \
    "$USR/share/icons/WhiteSur-dark/index.theme"; do
    [[ -f "$path" ]] || {
        echo "[ERROR]: expected Liquid Glass asset was not staged: $path" >&2
        exit 1
    }
done

echo "[INFO]: KDE Liquid Glass theme and KWin components staged successfully"
