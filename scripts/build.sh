#!/bin/bash
set -Eeuo pipefail

# Set the version from the current build date and the channel entered by the user.
BUILD_DATE="$(date +%y.%m.%d)"
PROFILE_VERSION_FILE="$(pwd)/profile/version"

if [[ ! -f "$PROFILE_VERSION_FILE" ]]; then
    echo "[ERROR]: profile/version was not found. Run this script from the repository root." >&2
    exit 1
fi

while true; do
    read -r -p "Enter release channel/suffix (e.g. stable, beta, indev, indev.xxx): " release_channel

    if [[ "$release_channel" =~ ^[a-z][a-z0-9-]*$ || "$release_channel" =~ ^[a-z][a-z0-9-]*\.[a-z0-9-]+$ ]]; then
        break
    fi

    echo "[ERROR]: invalid channel. Use lowercase letters/numbers/hyphens, optionally followed by .N (e.g. indev.xxx)." >&2
done

mulios_version="${BUILD_DATE}-${release_channel}"
release_branch="${release_channel%%.*}"
case "$release_branch" in
    stable|beta|indev) ;;
    *) release_branch="unknown" ;;
esac
printf '%s\n' "$mulios_version" > "$PROFILE_VERSION_FILE"
echo "[INFO]: building MuliOS version $mulios_version"

install_dependencies() {
    echo "[INFO]: installing dependencies"

    if command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --needed --noconfirm \
            archiso git base-devel squashfs-tools mtools dosfstools libisoburn curl \
            cmake extra-cmake-modules qt6-tools vulkan-headers kwin

        if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
            echo "[INFO]: installing KDE Liquid Glass build dependencies"
            sudo pacman -S --needed --noconfirm \
                qt6-base qt6-declarative qt6-svg kdecoration kconfig kconfigwidgets \
                kcoreaddons kcolorscheme kcmutils kcrash kglobalaccel kguiaddons \
                kiconthemes kio kirigami knotifications kpackage kservice ki18n \
                kwindowsystem frameworkintegration libepoxy libdrm libxcb wayland
        fi
    else
        echo "[ERROR]: not in an Arch Linux environment"
        exit 1
    fi
}

install_dependencies

setup() {
    export WORK_DIR="$(pwd)"
    export PROFILE="$WORK_DIR/profile"
    export MULIOS_THEME_VARIANT="${MULIOS_THEME_VARIANT:-rounded}"
    export OUTPUT="$WORK_DIR/output"
    export TEMP="$WORK_DIR/temp"
    export PACKAGE_REPO="$PROFILE/packages"
    export BUILD_DIR="$WORK_DIR/.build"
    export PACMAN_CONFIG="$BUILD_DIR/pacman.conf"

    echo "[INFO]: Checking build directories"

    mkdir -p "$OUTPUT" "$TEMP" "$BUILD_DIR"
}

setup

echo "[INFO]: refreshing local MuliOS package database"
bash "$WORK_DIR/scripts/refresh-local-repo.sh" "$PACKAGE_REPO"

PACKAGE_REPO="$PACKAGE_REPO" PACMAN_CONFIG="$PACMAN_CONFIG" SOURCE_CONFIG="$PROFILE/pacman.conf" python3 - <<'PY'
import os
from pathlib import Path

source = Path(os.environ["SOURCE_CONFIG"]).read_text()
repo = Path(os.environ["PACKAGE_REPO"]).resolve().as_posix()
if "@MULIOS_PACKAGE_REPO@" not in source:
    raise SystemExit("profile/pacman.conf is missing @MULIOS_PACKAGE_REPO@")
Path(os.environ["PACMAN_CONFIG"]).write_text(
    source.replace("@MULIOS_PACKAGE_REPO@", f"file://{repo}")
)
PY

VERSION_TEMPLATE_FILES=(
    "$PROFILE/grub/grub.cfg"
    "$PROFILE/efiboot/loader/entries/01-archiso-linux.conf"
    "$PROFILE/efiboot/loader/entries/02-archiso-speech-linux.conf"
    "$PROFILE/syslinux/archiso_sys-linux.cfg"
)
VERSION_TEMPLATE_BACKUP_DIR=""

restore_version_templates() {
    [[ -n "$VERSION_TEMPLATE_BACKUP_DIR" && -d "$VERSION_TEMPLATE_BACKUP_DIR" ]] || return 0

    local index=0
    local file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        cp "$VERSION_TEMPLATE_BACKUP_DIR/$index" "$file"
        index=$((index + 1))
    done

    rm -rf "$VERSION_TEMPLATE_BACKUP_DIR"
    VERSION_TEMPLATE_BACKUP_DIR=""
}

trap restore_version_templates EXIT

normalize_version_templates() {
    # A previous interrupted/older build may have left a literal release version
    # in the source templates. Canonicalize those lines back to the placeholder
    # before backing them up, so the EXIT trap always restores reusable templates.
    local file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        sed -E -i \
            -e 's/(MuliOS )[0-9]{2}\.[0-9]{2}\.[0-9]{2}-[a-z][a-z0-9-]*(\.[0-9]+)?/\1@MULIOS_VERSION@/g' \
            "$file"
    done
}

prepare_version_templates() {
    normalize_version_templates
    VERSION_TEMPLATE_BACKUP_DIR="$(mktemp -d "$WORK_DIR/.version-templates.XXXXXX")"

    local index=0
    local file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        cp "$file" "$VERSION_TEMPLATE_BACKUP_DIR/$index"
        index=$((index + 1))
    done

    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        sed -i "s/@MULIOS_VERSION@/$mulios_version/g" "$file"
    done
}

build() {
    local mulios_version
    mulios_version="$(cat "$PROFILE/version")"

    if [[ ! "$mulios_version" =~ ^[0-9]{2}\.[0-9]{2}\.[0-9]{2}-[a-z][a-z0-9-]*$ && ! "$mulios_version" =~ ^[0-9]{2}\.[0-9]{2}\.[0-9]{2}-[a-z][a-z0-9-]*\.[0-9]+$ ]]; then
        echo "[ERROR]: invalid MuliOS version '$mulios_version'." >&2
        echo "[ERROR]: expected YY.MM.DD-CHANNEL, optionally followed by .N." >&2
        exit 1
    fi

    local theme_builder="${MULIOS_THEME_BUILDER:-$WORK_DIR/scripts/install-rounded-theme.sh}"
    if [[ ! -f "$theme_builder" ]]; then
        echo "[ERROR]: theme installer not found: $theme_builder" >&2
        exit 1
    fi
    bash "$theme_builder"
    if [[ "$MULIOS_THEME_VARIANT" == "liquid-glass" ]]; then
        echo "[INFO]: skipping third-party KWin effects for Liquid Glass safe boot"
    else
        bash "$WORK_DIR/scripts/build-kwin-effects.sh"
    fi

    # The Rust task manager binary is built before packaging and included in airootfs.
    local taskmanager_binary="$PROFILE/airootfs/usr/bin/mulios-taskmanager"
    if [[ ! -x "$taskmanager_binary" ]]; then
        echo "[ERROR] Compiled Rust Task Manager is missing or not executable: $taskmanager_binary" >&2
        exit 1
    fi

    prepare_version_templates

    # Add a trusted Task Manager shortcut to the live user's desktop.
    install -D -m 0755 \
        "$PROFILE/airootfs/usr/share/applications/taskmanager.desktop" \
        "$PROFILE/airootfs/etc/skel/Desktop/taskmanager.desktop"

    # Desktop launchers must be executable for Plasma to treat them as trusted
    # launchable desktop entries in the live session.
    chmod 0755 "$PROFILE/airootfs/usr/local/bin/mulios-installer"
    chmod 0755 "$PROFILE/airootfs/usr/local/bin/mulios-taskmanager"
    chmod 0755 "$taskmanager_binary"
    chmod 0755 "$PROFILE/airootfs/usr/local/bin/mulios-credits"
    chmod 0755 "$PROFILE/airootfs/usr/local/bin/mulios-apply-wallpaper"
    chmod 0755 "$PROFILE/airootfs/usr/local/bin/mulios-wallpaper-autostart"
    chmod 0755 "$PROFILE/airootfs/usr/local/bin/fastfetch"
    chmod 0755 "$PROFILE/airootfs/etc/skel/Desktop/mulios-installer.desktop"
    chmod 0755 "$PROFILE/airootfs/usr/share/applications/mulios-installer.desktop"

    MULIOS_ROOT="$WORK_DIR" bash "$WORK_DIR/scripts/test.sh"

    cat > "$PROFILE/airootfs/etc/os-release" <<EOF
NAME="MuliOS"
PRETTY_NAME="MuliOS Arch $mulios_version"
ID=mulios
ID_LIKE=arch
VERSION="$mulios_version"
VERSION_ID="$mulios_version"
BUILD_ID="$mulios_version"
ANSI_COLOR="38;2;0;103;56"
HOME_URL="https://github.com/MuliOS-dev"
IMAGE_ID=MuliOS
IMAGE_VERSION="$mulios_version"
MULIOS_RELEASE_BRANCH="$release_branch"
EOF

    sudo env MULIOS_PACMAN_CONF="$PACMAN_CONFIG" mkarchiso -v -w "$TEMP" -o "$OUTPUT" "$PROFILE"
}

build

echo "[INFO]: build complete! the ISO is in output dir"
ls -lh "$OUTPUT"
