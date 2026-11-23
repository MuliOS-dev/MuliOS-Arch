#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d "$ROOT/.git" ]]; then
    printf 'ERROR: MuliOS source checkout not found.\n' >&2
    exit 1
fi

if [[ "${MULIOS_PREPARE_PULL:-0}" == "1" ]]; then
    git pull --ff-only
fi

exec bash "$ROOT/scripts/build.sh"
