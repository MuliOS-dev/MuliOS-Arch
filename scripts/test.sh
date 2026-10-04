#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$ROOT/profile"

usage() {
    cat <<'EOF'
Usage:
  ./scripts/test.sh
  ./scripts/test.sh --clean

Runs static MuliOS profile checks without building the ISO.
--clean removes generated build output and temporary directories.
EOF
}

if [[ "${1:-}" == "--clean" ]]; then
    rm -rf "$ROOT/output" "$ROOT/temp" "$ROOT/work" "$ROOT/out"
    echo "[OK] Build artifacts removed."
    exit 0
fi

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

fail=0

check_file() {
    local path="$1"
    if [[ ! -e "$path" ]]; then
        echo "[FAIL] Missing: $path"
        fail=1
    else
        echo "[OK] $path"
    fi
}

check_executable() {
    local path="$1"
    if [[ ! -x "$path" ]]; then
        echo "[FAIL] Not executable: $path"
        fail=1
    else
        echo "[OK] executable: $path"
    fi
}

echo "== MuliOS static profile checks =="

for path in \
    "$PROFILE/profiledef.sh" \
    "$PROFILE/packages.x86_64" \
    "$PROFILE/grub/grub.cfg" \
    "$PROFILE/efiboot/loader" \
    "$PROFILE/syslinux/syslinux.cfg" \
    "$PROFILE/airootfs/usr/share/backgrounds/mulios/wallpaper.png" \
    "$PROFILE/airootfs/usr/share/wallpapers/MuliOS/wallpaper.png" \
    "$PROFILE/airootfs/etc/xdg/autostart/mulios-wallpaper.desktop" \
    "$PROFILE/airootfs/usr/share/applications/taskmanager.desktop" \
    "$PROFILE/airootfs/usr/share/applications/mulios-credits.desktop"
do
    check_file "$path"
done

for path in \
    "$PROFILE/airootfs/usr/local/bin/mulios-installer" \
    "$PROFILE/airootfs/usr/local/bin/mulios-taskmanager" \
    "$PROFILE/airootfs/usr/local/bin/mulios-credits" \
    "$PROFILE/airootfs/usr/local/bin/mulios-apply-wallpaper" \
    "$PROFILE/airootfs/usr/local/bin/mulios-wallpaper-autostart"
do
    check_executable "$path"
done

if command -v bash >/dev/null 2>&1; then
    while IFS= read -r -d '' file; do
        if bash -n "$file"; then
            echo "[OK] shell syntax: $file"
        else
            echo "[FAIL] shell syntax: $file"
            fail=1
        fi
    done < <(find "$ROOT/scripts" "$PROFILE/airootfs/usr/local/bin" "$PROFILE/airootfs/root" -type f -name '*.sh' -print0)
fi

if command -v python3 >/dev/null 2>&1; then
    while IFS= read -r -d '' file; do
        if python3 -m py_compile "$file"; then
            echo "[OK] python syntax: $file"
        else
            echo "[FAIL] python syntax: $file"
            fail=1
        fi
    done < <(find "$PROFILE/airootfs/opt" -type f -name '*.py' -print0)
fi

if command -v node >/dev/null 2>&1; then
    if node --check "$PROFILE/airootfs/opt/taskmanager/main.js"; then
        echo "[OK] node syntax: task manager backend"
    else
        echo "[FAIL] node syntax: task manager backend"
        fail=1
    fi
fi

if command -v desktop-file-validate >/dev/null 2>&1; then
    while IFS= read -r -d '' file; do
        if desktop-file-validate "$file"; then
            echo "[OK] desktop entry: $file"
        else
            echo "[FAIL] desktop entry: $file"
            fail=1
        fi
    done < <(find "$PROFILE/airootfs/usr/share/applications" "$PROFILE/airootfs/etc/xdg/autostart" "$PROFILE/airootfs/etc/skel/Desktop" -type f -name '*.desktop' -print0)
fi

if grep -RInE 'wallpaper\.(jpg|jpeg)' "$PROFILE/airootfs" "$ROOT/docs" >/dev/null 2>&1; then
    echo "[FAIL] stale wallpaper.jpg reference found"
    fail=1
else
    echo "[OK] no stale wallpaper.jpg references"
fi

if grep -RInE 'Exec=/usr/bin/python3 /opt/(taskmanager|credits)' "$PROFILE/airootfs/usr/share/applications" >/dev/null 2>&1; then
    echo "[FAIL] application desktop entries bypass the MuliOS launch wrappers"
    fail=1
else
    echo "[OK] application desktop entries use MuliOS launch wrappers"
fi

if ! grep -q '^nodejs$' "$PROFILE/packages.x86_64"; then
    echo "[FAIL] nodejs is missing from the live package set"
    fail=1
else
    echo "[OK] nodejs is included"
fi

if [[ "$fail" -ne 0 ]]; then
    echo "Static checks failed."
    exit 1
fi

echo "All static checks passed."
