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

    echo "[INFO] Fetching optional KWin effect: $name"
    if ! git clone --depth 1 "$repo" "$source"; then
        echo "[WARN] Could not fetch $name; continuing without this optional effect."
        return 0
    fi

    echo "[INFO] Configuring $name against the build host's installed KWin/Qt libraries"
    local -a cmake_options=(-DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr)
    # Arch's current KWin development setup targets Wayland. Avoid enabling
    # optional X11 plugin paths that require separate KWinX11 components.
    case "$name" in
        betterblur_dx) cmake_options+=(-DBBDX_X11=OFF) ;;
        glass)     cmake_options+=(-DGLASS_X11=OFF) ;;
    esac

    if ! cmake -S "$source" -B "$build" "${cmake_options[@]}"; then
        echo "[WARN] $name is incompatible with the current KWin/Qt development libraries; continuing without it."
        return 0
    fi

    echo "[INFO] Compiling $name"
    if ! cmake --build "$build" --parallel "$(nproc)"; then
        echo "[WARN] $name failed to compile against the current KWin API; continuing without it."
        return 0
    fi

    echo "[INFO] Bundling $name into the MuliOS live filesystem"
    if ! DESTDIR="$ROOTFS" cmake --install "$build"; then
        echo "[WARN] Could not install $name; continuing without it."
        return 0
    fi

    echo "[INFO] Successfully bundled $name"
}

# Better Blur DX tracks newer KWin APIs; build it from its active upstream repository. Treat both
# effects as optional so a third-party plugin failure never blocks ISO creation.
build_effect "https://github.com/xarblu/kwin-effects-better-blur-dx" "betterblur_dx"
build_effect "https://github.com/4v3ngR/kwin-effects-glass" "glass"

echo "[INFO] Finished optional KWin effect builds. Check warnings above for effects that were skipped."
