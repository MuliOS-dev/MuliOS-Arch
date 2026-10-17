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
    read -r -p "Enter release channel/suffix (e.g. stable, beta, indev, indev.11): " release_channel

    if [[ "$release_channel" =~ ^[a-z][a-z0-9-]*(\.[0-9]+)?$ ]]; then
        break
    fi

    echo "[ERROR]: invalid channel. Use lowercase letters/numbers/hyphens, optionally followed by .N (e.g. indev.11)." >&2
done

mulios_version="${BUILD_DATE}-${release_channel}"
printf '%s\\n' "$mulios_version" > "$PROFILE_VERSION_FILE"
echo "[INFO]: building MuliOS version $mulios_version"

install_dependencies() {
    echo "[INFO]: installing dependencies"

    if command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --needed --noconfirm \
            archiso git base-devel squashfs-tools mtools dosfstools libisoburn curl
    else
        echo "[ERROR]: not in an Arch Linux environment"
        exit 1
    fi
}

install_dependencies

setup() {
    export WORK_DIR="$(pwd)"
    export PROFILE="$WORK_DIR/profile"
    export OUTPUT="$WORK_DIR/output"
    export TEMP="$WORK_DIR/temp"

    echo "[INFO]: Checking build directories"

    mkdir -p "$OUTPUT" "$TEMP"
}

setup

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

prepare_version_templates() {
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

    if [[ ! "$mulios_version" =~ ^[0-9]{2}\.[0-9]{2}\.[0-9]{2}-[a-z][a-z0-9-]*(\.[0-9]+)?$ ]]; then
        echo "[ERROR]: invalid MuliOS version '$mulios_version'." >&2
        echo "[ERROR]: expected YY.MM.DD-CHANNEL, optionally followed by .N." >&2
        exit 1
    fi

    "$WORK_DIR/scripts/install-rounded-theme.sh"
    prepare_version_templates

    # Desktop launchers must be executable for Plasma to treat them as trusted
    # launchable desktop entries in the live session.
    chmod 0755 "$PROFILE/airootfs/usr/local/bin/mulios-installer"
    chmod 0755 "$PROFILE/airootfs/usr/local/bin/mulios-taskmanager"
    chmod 0755 "$PROFILE/airootfs/usr/local/bin/mulios-credits"
    chmod 0755 "$PROFILE/airootfs/usr/local/bin/mulios-apply-wallpaper"
    chmod 0755 "$PROFILE/airootfs/usr/local/bin/mulios-wallpaper-autostart"
    chmod 0755 "$PROFILE/airootfs/usr/local/bin/fastfetch"
    chmod 0755 "$PROFILE/airootfs/etc/skel/Desktop/mulios-installer.desktop"
    chmod 0755 "$PROFILE/airootfs/usr/share/applications/mulios-installer.desktop"

    bash "$WORK_DIR/scripts/test.sh"

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
EOF

    sudo mkarchiso -v -w "$TEMP" -o "$OUTPUT" "$PROFILE"
}

build

echo "[INFO]: build complete! the ISO is in output dir"
ls -lh "$OUTPUT"
