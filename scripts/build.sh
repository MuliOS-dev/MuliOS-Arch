#!/bin/bash
set -Eeuo pipefail

install_dependencies() {
    echo "[INFO]: installing dependencies"

    if command -v pacman &> /dev/null; then
      sudo pacman -S --needed --noconfirm archiso git

    else echo -e "[ERROR]: not in archlinux enviroment , please use archlinux or using virtual machine for this"
    exit 1
  fi 
}
install_dependencies

setup() {
export WORK_DIR=$(pwd)
export PROFILE="$WORK_DIR/profile"

echo -e "[INFO]: Checking and setup"
if [ -d "$WORK_DIR/output" ]; then 
  echo "[+]: found output dir"
else 
  echo "[-]: cant found output dir , creating..."
  mkdir -p "$WORK_DIR"/output
fi

if [ -d "$WORK_DIR/temp" ]; then 
  echo "[+]: found temp dir"
else 
  echo "[-]: cant found temp dir , creating..."
  mkdir -p "$WORK_DIR"/temp
fi

export OUTPUT="$WORK_DIR/output"
export TEMP="$WORK_DIR/temp"
}
setup

build() {
MULIOS_VERSION="$(cat "$PROFILE/version")"

cat > "$PROFILE/airootfs/etc/os-release" <<EOF
NAME="MulioS"
PRETTY_NAME="MuliOS Arch $MULIOS_VERSION"
ID=mulios
ID_LIKE=arch
VERSION="$MULIOS_VERSION"
VERSION_ID="$MULIOS_VERSION"
BUILD_ID="$MULIOS_VERSION"
ANSI_COLOR="38;2;0;103;56"
HOME_URL="https://github.com/MuliOS-dev"
IMAGE_ID=MulioS
IMAGE_VERSION="$MULIOS_VERSION"
EOF

sudo mkarchiso -v -w "$TEMP" -o "$OUTPUT" "$PROFILE" -c
}
build

echo "[INFO]: build complete! the iso is in output dir"
ls "$OUTPUT"
