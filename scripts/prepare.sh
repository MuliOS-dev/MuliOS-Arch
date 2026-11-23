#!/bin/bash

if [ "$BUILD_DONE" != "1" ]; then
  export SETUP_DONE=1
  echo "[INFO]: Running setup..."

  install_dependencies() {
    echo "[INFO]: Installing dependencies"

    if command -v pacman &>/dev/null; then
      sudo pacman -S --needed archiso git base-devel squashfs-tools mtools dosfstools libisoburn

    else
      echo "[ERROR]: Not in archlinux enviroment, please use archlinux or a virtual machine for this."
      exit 1
    fi
  }
  install_dependencies

  setup() {
    export WORK_DIR=$(pwd)
    export PROFILE="$WORK_DIR/profile"

    echo "[INFO]: Updating the OS code..."
    cd $WORK_DIR

    if ! git pull; then
      echo "[Error]: git pull failed."
      exit 1
    fi

    echo "[INFO]: Checking and setup"
    if [ -d "$WORK_DIR/output" ]; then
      echo "[+]: Found output dir"
    else
      echo "[-]: Cannot find output dir, creating..."
      mkdir -p "$WORK_DIR/output"
    fi

    if [ -d "$WORK_DIR/temp" ]; then
      echo "[+]: Found temp dir"
    else
      echo "[-]: Cannot find temp dir, creating..."
      mkdir -p "$WORK_DIR/temp"
    fi

    export OUTPUT="$WORK_DIR/output"
    export TEMP="$WORK_DIR/temp"
  }
  setup

  echo "[INFO]: Build start"
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOUCRE[0]}")")" && pwd
  EXPECT_DIR="$WORK_DIR/scripts"

  if ["$SCRIPT_DIR" != "$TARGET_DIR"]; then
    echo "[ERROR]: Please but the prepare.sh in $EXPECT_DIR"
    exit 1
  else
    "$WORK_DIR/build.sh"
  fi

fi
