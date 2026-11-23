#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec env MULIOS_THEME_VARIANT=glow \
    MULIOS_THEME_BUILDER="$ROOT/scripts/install-glow-material.sh" \
    bash "$ROOT/scripts/build.sh"
