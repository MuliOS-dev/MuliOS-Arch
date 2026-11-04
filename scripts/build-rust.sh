#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PROFILE_ROOT="$WORK_DIR/profile/airootfs"
TARGET_DIR="$WORK_DIR/temp/rust-target"
BINARY="$TARGET_DIR/release/muliosctl"

if ! command -v cargo >/dev/null 2>&1; then
    echo "[ERROR] Cargo is required to build MuliOS Rust applications." >&2
    exit 1
fi

if [[ ! -f "$WORK_DIR/Cargo.toml" ]]; then
    echo "[ERROR] Cargo workspace manifest not found: $WORK_DIR/Cargo.toml" >&2
    exit 1
fi

echo "[INFO] Building MuliOS Rust workspace..."
cargo build --manifest-path "$WORK_DIR/Cargo.toml" --workspace --release --target-dir "$TARGET_DIR"

if [[ ! -x "$BINARY" ]]; then
    echo "[ERROR] Expected Rust executable was not produced: $BINARY" >&2
    exit 1
fi

install -D -m 0755 "$BINARY" "$PROFILE_ROOT/usr/local/bin/muliosctl"
echo "[OK] Staged muliosctl in the Archiso live filesystem."
"$PROFILE_ROOT/usr/local/bin/muliosctl" version
