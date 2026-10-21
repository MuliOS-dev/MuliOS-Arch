#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${MULIOS_ROOT:-$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)}"
if [[ -z "$ROOT" ]]; then
    ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
fi
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

if ! grep -q '^kdialog$' "$PROFILE/packages.x86_64"; then
    echo "[FAIL] kdialog is missing; application startup failures would be silent"
    fail=1
else
    echo "[OK] kdialog is included for application startup diagnostics"
fi

check_desktop_launcher() {
    local desktop_file="$1"
    local expected="$2"
    local exec_value tryexec_value
    exec_value="$(sed -n 's/^Exec=//p' "$desktop_file" | head -n 1)"
    tryexec_value="$(sed -n 's/^TryExec=//p' "$desktop_file" | head -n 1)"
    if [[ "$exec_value" == "$expected" && "$tryexec_value" == "$expected" && -x "$PROFILE/airootfs$expected" ]]; then
        echo "[OK] desktop entry launches executable wrapper: $desktop_file"
    else
        echo "[FAIL] desktop entry does not point to its executable wrapper: $desktop_file"
        fail=1
    fi
}

check_desktop_launcher "$PROFILE/airootfs/usr/share/applications/taskmanager.desktop" "/usr/local/bin/mulios-taskmanager"
check_desktop_launcher "$PROFILE/airootfs/usr/share/applications/mulios-credits.desktop" "/usr/local/bin/mulios-credits"

if ! grep -q 'mulios-state-' "$PROFILE/airootfs/usr/local/bin/mulios-taskmanager" ||
   ! grep -q 'gettempdir' "$PROFILE/airootfs/opt/taskmanager/launcher.py"; then
    echo "[FAIL] Task Manager has no writable fallback for state/log directory"
    fail=1
else
    echo "[OK] Task Manager falls back when the user's state directory is not writable"
fi

if ! grep -q 'const PORT' "$PROFILE/airootfs/opt/taskmanager/main.js" ||
   ! grep -q 'const URL' "$PROFILE/airootfs/opt/taskmanager/main.js"; then
    echo "[FAIL] Task Manager backend is missing its host/port configuration"
    fail=1
else
    echo "[OK] Task Manager backend defines its listening host and port"
fi

if ! grep -q 'prepare_profile_kernel_conflicts' "$PROFILE/airootfs/usr/local/bin/mupdate" ||
   ! grep -q 'Refusing to move game-kernel header files' "$PROFILE/airootfs/usr/local/bin/mupdate" ||
   ! grep -q 'prepare_profile_kernel_conflicts' "$PROFILE/airootfs/opt/mulios-installer/mupdate"; then
    echo "[FAIL] MUpdate does not safely quarantine unowned game-kernel header conflicts"
    fail=1
else
    echo "[OK] MUpdate guards and quarantines stale unowned game-kernel header conflicts"
fi

if ! grep -q 'See /var/log/mulios/install.log' "$PROFILE/airootfs/opt/mulios-installer/backend/native_installer_worker.py"; then
    echo "[FAIL] Installer does not expose the underlying profile failure details"
    fail=1
else
    echo "[OK] Installer profile errors include the underlying failure details"
fi

if ! grep -q 'media.githubusercontent.com/media' "$PROFILE/airootfs/usr/local/bin/mupdate" ||
   ! grep -q 'Git LFS profile package integrity check failed' "$PROFILE/airootfs/usr/local/bin/mupdate"; then
    echo "[FAIL] MUpdate does not verify and retrieve Git LFS profile archives"
    fail=1
else
    echo "[OK] MUpdate verifies Git LFS profile archive payloads"
fi

if ! grep -q 'BreezeDark' "$PROFILE/airootfs/opt/mulios-installer/backend/native_installer_worker.py" ||
   ! grep -q 'org.kde.breeze' "$PROFILE/airootfs/opt/mulios-installer/backend/native_installer_worker.py"; then
    echo "[FAIL] Custom blur effects do not replace ROUNDED-DARK with the Breeze appearance preset"
    fail=1
else
    echo "[OK] Custom blur effects select a Breeze appearance preset"
fi

if ! grep -q 'mulios-state-' "$PROFILE/airootfs/usr/local/bin/mulios-credits"; then
    echo "[FAIL] Credits launcher has no writable fallback for its log directory"
    fail=1
else
    echo "[OK] Credits launcher falls back when the user's state directory is not writable"
fi

if ! grep -q 'backend_is_ready' "$PROFILE/airootfs/opt/taskmanager/launcher.py" ||
   ! grep -q 'BACKEND_START_TIMEOUT' "$PROFILE/airootfs/opt/taskmanager/launcher.py"; then
    echo "[FAIL] Task Manager does not wait for HTTP backend readiness"
    fail=1
else
    echo "[OK] Task Manager waits for backend readiness before showing the window"
fi

if grep -qE 'openStandaloneWindow|execFileSync|xdg-open' "$PROFILE/airootfs/opt/taskmanager/main.js"; then
    echo "[FAIL] Task Manager backend still tries to launch a second external browser"
    fail=1
else
    echo "[OK] Task Manager backend only serves the UI embedded by its Qt launcher"
fi

if ! grep -q '"express"' "$PROFILE/airootfs/opt/taskmanager/package.json" ||
   ! grep -q '"systeminformation"' "$PROFILE/airootfs/opt/taskmanager/package.json"; then
    echo "[FAIL] Task Manager runtime dependencies are missing from package.json"
    fail=1
else
    echo "[OK] Task Manager runtime dependencies are declared"
fi

if ! grep -q 'npm install --prefix "$taskmanager_dir"' "$ROOT/scripts/build.sh"; then
    echo "[FAIL] Task Manager npm dependencies are not bundled during ISO build"
    fail=1
else
    echo "[OK] Task Manager dependencies are bundled during ISO build"
fi

if ! grep -q 'shutil.which("qdbus6") or shutil.which("qdbus")' "$PROFILE/airootfs/opt/mulios-installer/main.py"; then
    echo "[FAIL] Desktop effect preview does not support qdbus6"
    fail=1
else
    echo "[OK] Desktop effect preview supports qdbus6 and qdbus"
fi

PROFILE_PAGE="$PROFILE/airootfs/opt/mulios-installer/pages/profile_page.py"
if ! grep -q 'https://api.github.com/repos/MuliOS-dev/update/git/trees/main?recursive=1' "$PROFILE_PAGE" ||
   ! grep -q 'class _ProfileFetchWorker' "$PROFILE_PAGE" ||
   ! grep -q 'thread.started.connect(worker.run)' "$PROFILE_PAGE"; then
    echo "[FAIL] Profile refresh must use MuliOS-dev/update asynchronously"
    fail=1
else
    echo "[OK] Profile refresh uses the requested repository and runs asynchronously"
fi

INSTALLER_MAIN="$PROFILE/airootfs/opt/mulios-installer/main.py"
if ! grep -q 'org.kde.kwin.Effects.loadEffect' "$INSTALLER_MAIN" ||
   ! grep -q 'org.kde.kwin.Effects.isEffectLoaded' "$INSTALLER_MAIN"; then
    echo "[FAIL] Desktop effect preview does not load and verify the effect through KWin D-Bus"
    fail=1
else
    echo "[OK] Desktop effect preview loads and verifies KWin effects through D-Bus"
fi

if ! grep -q 'self.profile_refresh_button.setVisible(index == IDX_PROFILE)' "$INSTALLER_MAIN" ||
   ! grep -q 'self.refresh_effects_button.setVisible(index == IDX_DESKTOP)' "$INSTALLER_MAIN"; then
    echo "[FAIL] Profile and desktop refresh buttons are not placed in the navigation footer"
    fail=1
else
    echo "[OK] Profile and desktop refresh buttons are shown in the navigation footer"
fi

KSPLASH="$PROFILE/airootfs/etc/skel/.config/ksplashrc"
if ! grep -Fxq 'Engine=none' "$KSPLASH" || ! grep -Fxq 'Theme=None' "$KSPLASH"; then
    echo "[FAIL] KDE splash animation is not disabled in the default user configuration"
    fail=1
else
    echo "[OK] KDE splash animation defaults to None"
fi

if grep -Fq '\\n' "$PROFILE/airootfs/opt/mulios-installer/backend/native_installer_worker.py"; then
    echo "[FAIL] Installer worker contains literal escaped newlines in generated configuration"
    fail=1
else
    echo "[OK] Installer worker uses real newline escapes for generated configuration"
fi

if ! grep -q 'DBUS_SESSION_BUS_ADDRESS=unix:path=' "$PROFILE/airootfs/opt/mulios-installer/main.py" ||
   ! grep -q 'runuser, "-u", desktop_user.pw_name' "$PROFILE/airootfs/opt/mulios-installer/main.py"; then
    echo "[FAIL] KWin preview does not target the active desktop user's D-Bus session"
    fail=1
else
    echo "[OK] KWin preview targets the active desktop user's D-Bus session"
fi

if ! head -n 1 "$PROFILE/airootfs/opt/credits/main.py" | grep -q '^#!/usr/bin/env python3$'; then
    echo "[FAIL] Credits must declare its Python interpreter"
    fail=1
else
    echo "[OK] Credits declares its Python interpreter"
fi

if ! grep -q 'def preview_desktop_effect' "$PROFILE/airootfs/opt/mulios-installer/main.py"; then
    echo "[FAIL] Desktop effect preview handler is missing"
    fail=1
else
    echo "[OK] Desktop effect preview handler exists"
fi

KERNEL_WORKER="$PROFILE/airootfs/opt/mulios-installer/backend/native_installer_worker.py"
if ! grep -q 'Path("/usr/lib/modules") / running_release / "vmlinuz"' "$KERNEL_WORKER" ||
   ! grep -q 'Kernel search paths checked:' "$KERNEL_WORKER"; then
    echo "[FAIL] Installer kernel discovery fallback or diagnostics are missing"
    fail=1
else
    echo "[OK] Installer checks the bundled kernel package image and logs search paths"
fi

expected_version="$(cat "$ROOT/profile/version" 2>/dev/null || true)"
for template in \
    "$PROFILE/grub/grub.cfg" \
    "$PROFILE/efiboot/loader/entries/01-archiso-linux.conf" \
    "$PROFILE/efiboot/loader/entries/02-archiso-speech-linux.conf" \
    "$PROFILE/syslinux/archiso_sys-linux.cfg"
do
    if grep -q '@MULIOS_VERSION@' "$template"; then
        echo "[OK] dynamic version placeholder: $template"
    elif [[ -n "$expected_version" ]] && grep -Fq "$expected_version" "$template"; then
        # During a build, build.sh temporarily substitutes the version before
        # running these checks, then restores the original source templates.
        echo "[OK] substituted build version: $template"
    else
        echo "[FAIL] Boot menu template has neither the version placeholder nor the current build version: $template"
        fail=1
    fi
done

if grep -RIn '26\.10\.20-indev\.11' \
    "$PROFILE/grub/grub.cfg" \
    "$PROFILE/efiboot/loader/entries" \
    "$PROFILE/syslinux/archiso_sys-linux.cfg" >/dev/null 2>&1; then
    echo "[FAIL] hardcoded stale version found in a boot menu template"
    fail=1
else
    echo "[OK] no hardcoded stale version in boot menu templates"
fi

if ! grep -q 'xarblu/kwin-effects-better-blur-dx' "$ROOT/scripts/build-kwin-effects.sh" ||
   ! grep -q 'Better Blur DX' "$PROFILE/airootfs/opt/mulios-installer/pages/desktop_page.py"; then
    echo "[FAIL] Better Blur DX build or installer selection is missing"
    fail=1
else
    echo "[OK] Better Blur DX build and installer selection are configured"
fi

if ! grep -q 'Continuing with the default desktop effects' "$PROFILE/airootfs/opt/mulios-installer/backend/native_installer_worker.py"; then
    echo "[FAIL] Offline desktop effect fallback is missing"
    fail=1
else
    echo "[OK] Offline desktop effect fallback exists"
fi

if [[ "$fail" -ne 0 ]]; then
    echo "Static checks failed."
    exit 1
fi

echo "All static checks passed."
