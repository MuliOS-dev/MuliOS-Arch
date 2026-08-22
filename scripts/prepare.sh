#!/bin/bash

if ["$BUILD_DONE" != "1" ]; then 
export SETUP_DONE=1
echo "[INFO]:Running setup..."

install_dependencies() {
    echo "[INFO]: installing dependencies"

    if command -v pacman &> /dev/null; then
      sudo pacman -S --needed --noconfirm archiso git base-devel squashfs-tools mtools dosfstools libisoburn

    else echo -e "[ERROR]: not in archlinux enviroment , please use archlinux or using virtual machine for this"
    exit 1
  fi 
}
install_dependencies

setup() {
export WORK_DIR=$(pwd)
export PROFILE="$WORK_DIR/profile"

echo -e "[INFO]:Updating the OS code..."
cd $WORK_DIR
git pull

echo -e "[INFO]: Checking and setup"
if [ -d "$WORK_DIR/output"]; then 
  echo "[+]: found output dir"
else 
  echo "[-]: cant found output dir , creating..."
  mkdir -p "$WORK_DIR"/output
fi

if [ -d "$WORK_DIR/temp"]; then 
  echo "[+]: found temp dir"
else 
  echo "[-]: cant found temp dir , creating..."
  mkdir -p "$WORK_DIR"/temp"
fi

export OUTPUT="$WORK_DIR/output"
export TEMP="$WORK_DIR/temp"
}
setup

echo -e "[INFO]:Build start]"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOUCRE[0]")" && pwd"
EXPECT_DIR="$WORK_DIR/scripts"

if ["$SCRIPT_DIR" != "$TARGET_DIR"]; then
  echo "[ERROR]:Please but the prepare.sh in $EXPECT_DIR"
  exit 1
fi

else 
  echo -e "[INFO]:Build start]"
  "$WORK_DIR/build.sh"
fi
