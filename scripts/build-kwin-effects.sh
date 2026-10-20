#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOTFS="$ROOT_DIR/profile/airootfs"
BUILD_DIR="${TMPDIR:-/tmp}/mulios-kwin-effects-build"

if ! command -v cmake >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
    echo "[ERROR] Missing KWin effect build dependencies. Run scripts/build.sh to install them." >&2
    exit 1
fi

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cleanup() {
    rm -rf "$BUILD_DIR"
}
trap cleanup EXIT

build_effect() {
    local repo="$1"
    local name="$2"
    local source="$BUILD_DIR/$name"
    local build="$BUILD_DIR/$name-build"

    echo "[INFO] Fetching $name"
    git clone --depth 1 "$repo" "$source"

    echo "[INFO] Configuring $name against the build host's installed KWin/Qt libraries"
    local -a cmake_options=(-DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr)
    # Arch's current KWin development setup targets Wayland. Avoid enabling
    # the optional X11 plugin path, which requires a separate KWinX11 package.
    case "$name" in
        forceblur) cmake_options+=(-DBETTERBLUR_X11=OFF) ;;
        glass)     cmake_options+=(-DGLASS_X11=OFF) ;;
    esac
    cmake -S "$source" -B "$build" "${cmake_options[@]}"

    echo "[INFO] Compiling $name"
    cmake --build "$build" --parallel "$(nproc)"

    echo "[INFO] Bundling $name into the MuliOS live filesystem"
    DESTDIR="$ROOTFS" cmake --install "$build"
}

build_effect "https://github.com/taj-ny/kwin-effects-forceblur" "forceblur"
build_effect "https://github.com/4v3ngR/kwin-effects-glass" "glass"

echo "[INFO] Both optional KWin effects are bundled in the live filesystem."
