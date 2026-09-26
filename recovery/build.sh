#!/bin/bash
set -Eeuo pipefail

sudo pacman -S --needed --noconfirm archiso

rm -rf output temp
mkdir -p output temp

sudo mkarchiso -v -w "$PWD/temp" -o "$PWD/output" "$PWD/profile"

echo "MuliRecovery ISO:"
ls -lh output/
