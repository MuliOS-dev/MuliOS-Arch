#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MULIOS_THEME_VARIANT=liquid-glass \
MULIOS_THEME_BUILDER="$ROOT/scripts/install-liquid-glass-theme.sh" \
    exec bash "$ROOT/scripts/build.sh"
