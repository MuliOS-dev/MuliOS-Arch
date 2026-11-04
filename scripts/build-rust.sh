#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PROFILE_ROOT="$WORK_DIR/profile/airootfs"
TARGET_DIR="$WORK_DIR/temp/rust-target"
BINARY="$TARGET_DIR/release/muliosctl"
TASKMANAGER_BINARY="$TARGET_DIR/release/mulios-taskmanager"

if ! command -v cargo >/dev/null 2>&1; then
    echo "[ERROR] Cargo is required to build MuliOS Rust applications." >&2
    exit 1
fi

if [[ ! -f "$WORK_DIR/Cargo.toml" ]]; then
    echo "[ERROR] Cargo workspace manifest not found: $WORK_DIR/Cargo.toml" >&2
    exit 1
fi

echo "[INFO] Building production MuliOS Rust utilities..."
cargo build --manifest-path "$WORK_DIR/Cargo.toml" -p muliosctl --release --target-dir "$TARGET_DIR"

if [[ ! -x "$BINARY" ]]; then
    echo "[ERROR] Expected Rust executable was not produced: $BINARY" >&2
    exit 1
fi

install -D -m 0755 "$BINARY" "$PROFILE_ROOT/usr/local/bin/muliosctl"
echo "[OK] Staged muliosctl in the Archiso live filesystem."
"$PROFILE_ROOT/usr/local/bin/muliosctl" version

# The new Task Manager backend is intentionally opt-in until it reaches full
# feature parity with the current production Node.js backend.
if [[ "${MULIOS_BUILD_EXPERIMENTAL_RUST_TASKMANAGER:-0}" == "1" ]]; then
    echo "[INFO] Building experimental native Task Manager backend..."
    cargo build --manifest-path "$WORK_DIR/Cargo.toml" -p mulios-taskmanager --release --target-dir "$TARGET_DIR"
    if [[ ! -x "$TASKMANAGER_BINARY" ]]; then
        echo "[ERROR] Expected Task Manager executable was not produced: $TASKMANAGER_BINARY" >&2
        exit 1
    fi
    install -D -m 0755 "$TASKMANAGER_BINARY" "$PROFILE_ROOT/usr/local/libexec/mulios-taskmanager-native"
    "$PROFILE_ROOT/usr/local/libexec/mulios-taskmanager-native" --version
fi
