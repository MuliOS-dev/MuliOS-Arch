#!/bin/bash
set -Eeuo pipefail

install_dependencies() {
    echo "[INFO]: installing dependencies"

    if command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --needed --noconfirm archiso git base-devel squashfs-tools mtools dosfstools libisoburn
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

build() {
    local mulios_version
    mulios_version="$(cat "$PROFILE/version")"

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
