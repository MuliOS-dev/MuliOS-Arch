#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    C_RESET=$'\033[0m'
    C_BOLD=$'\033[1m'
    C_DIM=$'\033[2m'
    C_BLUE=$'\033[34m'
    C_CYAN=$'\033[36m'
    C_GREEN=$'\033[32m'
    C_YELLOW=$'\033[33m'
    C_RED=$'\033[31m'
else
    C_RESET=''; C_BOLD=''; C_DIM=''; C_BLUE=''; C_CYAN=''
    C_GREEN=''; C_YELLOW=''; C_RED=''
fi

BUILD_ID="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/build-$BUILD_ID.log"
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

STEP=0
TOTAL_STEPS=7
STEP_STARTED_AT=$SECONDS
BUILD_STARTED_AT=$SECONDS
CURRENT_STEP="initialization"
VERSION_TEMPLATE_BACKUP_DIR=""
VERSION_TEMPLATE_FILES=()
OUTPUT="$ROOT/output"

log() {
    local color="$1" symbol="$2" level="$3"; shift 3
    printf '  %s%s%-2s%s %s%-7s%s %s\n' "$color" "$C_BOLD" "$symbol" "$C_RESET" "$color" "$level" "$C_RESET" "$*"
}
info()    { log "$C_CYAN" '›' INFO "$*"; }
success() { log "$C_GREEN" '✓' DONE "$*"; }
warning() { log "$C_YELLOW" '!' NOTE "$*"; }
error()   { log "$C_RED" '✖' ERROR "$*" >&2; }
step() {
    if (( STEP > 0 )); then
        printf '  %s✓ Step %02d finished in %02ds%s\n' "$C_GREEN" "$STEP" "$((SECONDS - STEP_STARTED_AT))" "$C_RESET"
    fi
    STEP=$((STEP + 1))
    STEP_STARTED_AT=$SECONDS
    CURRENT_STEP="$*"
    local filled=$((STEP * 24 / TOTAL_STEPS))
    local empty=$((24 - filled))
    printf -v bar '%*s' "$filled" ''
    bar="${bar// /━}"
    printf -v gap '%*s' "$empty" ''
    gap="${gap// /─}"
    printf '\n%s╭─ STEP %02d/%02d ───────────────────────────────────────────────╮%s\n' "$C_BOLD$C_BLUE" "$STEP" "$TOTAL_STEPS" "$C_RESET"
    printf '%s│%s %s%s%s\n' "$C_BLUE" "$C_RESET" "$C_BOLD" "$CURRENT_STEP" "$C_RESET"
    printf '%s│%s %s%s%s%s %s%2d%%%s\n' "$C_BLUE" "$C_RESET" "$C_GREEN" "$bar" "$C_DIM" "$gap" "$C_CYAN" "$((STEP * 100 / TOTAL_STEPS))" "$C_RESET"
    printf '%s╰────────────────────────────────────────────────────────────╯%s\n' "$C_BLUE" "$C_RESET"
}
run() {
    info "Running: $*"
    "$@"
}
restore_version_templates() {
    [[ -n "$VERSION_TEMPLATE_BACKUP_DIR" && -d "$VERSION_TEMPLATE_BACKUP_DIR" ]] || return 0
    local index=0 file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        cp "$VERSION_TEMPLATE_BACKUP_DIR/$index" "$file"
        index=$((index + 1))
    done
    rm -rf "$VERSION_TEMPLATE_BACKUP_DIR"
    VERSION_TEMPLATE_BACKUP_DIR=""
}
finish() {
    local status=$?
    restore_version_templates
    printf '\n'
    if (( status == 0 )); then
        if (( STEP > 0 )); then
            printf '  %s✓ Step %02d finished in %02ds%s\n' "$C_GREEN" "$STEP" "$((SECONDS - STEP_STARTED_AT))" "$C_RESET"
        fi
        local duration=$((SECONDS - BUILD_STARTED_AT))
        printf '\n%s╭──────────────────── BUILD SUCCESS ────────────────────╮%s\n' "$C_BOLD$C_GREEN" "$C_RESET"
        printf '%s│%s  Version:  %s%s%s\n' "$C_GREEN" "$C_RESET" "$C_BOLD" "${MULIOS_VERSION:-unknown}" "$C_RESET"
        printf '%s│%s  Duration: %02d:%02d\n' "$C_GREEN" "$C_RESET" "$((duration / 60))" "$((duration % 60))"
        printf '%s│%s  Output:   %s\n' "$C_GREEN" "$C_RESET" "$OUTPUT"
        printf '%s│%s  Log:      %s\n' "$C_GREEN" "$C_RESET" "$LOG_FILE"
        printf '%s╰────────────────────────────────────────────────────────╯%s\n' "$C_GREEN" "$C_RESET"
    else
        error "Build failed during: $CURRENT_STEP (exit $status)"
        error "Elapsed time: $(( (SECONDS - BUILD_STARTED_AT) / 60 ))m $(( (SECONDS - BUILD_STARTED_AT) % 60 ))s"
        error "Full log: $LOG_FILE"
    fi
    exit "$status"
}
trap finish EXIT

if [[ ! -f "$ROOT/profile/profiledef.sh" || ! -f "$ROOT/profile/packages.x86_64" ]]; then
    error "Run this script from a valid MuliOS-Arch checkout."
    exit 1
fi
if ! command -v pacman >/dev/null || ! command -v mkarchiso >/dev/null; then
    error "This build must run inside Arch Linux with pacman and archiso installed."
    exit 1
fi
if ! command -v sudo >/dev/null; then
    error "sudo is required to install build dependencies and run mkarchiso."
    exit 1
fi

OUTPUT="$ROOT/output"
TEMP="$ROOT/temp"
PACKAGE_REPO="$ROOT/profile/packages"
BUILD_DIR="$ROOT/.build"
mkdir -p "$OUTPUT" "$TEMP" "$BUILD_DIR"

printf '\n%s╭────────────────────────────────────────────────────────────╮%s\n' "$C_BOLD$C_CYAN" "$C_RESET"
printf '%s│%s  %sMuliOS%s  %sISO BUILD SYSTEM%s                               %s│%s\n' "$C_CYAN" "$C_RESET" "$C_BOLD" "$C_RESET" "$C_DIM" "$C_RESET" "$C_CYAN" "$C_RESET"
printf '%s╰────────────────────────────────────────────────────────────╯%s\n' "$C_CYAN" "$C_RESET"
printf '  %sBuild ID  %s%s\n' "$C_DIM" "$C_RESET" "$BUILD_ID"
printf '  %sTheme     %s%s\n' "$C_DIM" "$C_RESET" "${MULIOS_THEME_VARIANT:-rounded}"
printf '  %sWorkspace %s%s\n' "$C_DIM" "$C_RESET" "$ROOT"
printf '  %sLog       %s%s\n\n' "$C_DIM" "$C_RESET" "$LOG_FILE"

BUILD_DATE="$(date +%y.%m.%d)"
read -r -p "${C_BOLD}Release channel (stable, beta, indev, indev.xxx): ${C_RESET}" RELEASE_CHANNEL
if [[ ! "$RELEASE_CHANNEL" =~ ^[a-z][a-z0-9-]*([.][a-z0-9-]+)?$ ]]; then
    error "Invalid release channel."
    exit 1
fi
MULIOS_VERSION="$BUILD_DATE-$RELEASE_CHANNEL"
RELEASE_BRANCH="${RELEASE_CHANNEL%%.*}"
case "$RELEASE_BRANCH" in stable|beta|indev) ;; *) RELEASE_BRANCH="unknown" ;; esac

VERSION_TEMPLATE_FILES=(
    "$ROOT/profile/grub/grub.cfg"
    "$ROOT/profile/efiboot/loader/entries/01-archiso-linux.conf"
    "$ROOT/profile/efiboot/loader/entries/02-archiso-speech-linux.conf"
    "$ROOT/profile/syslinux/archiso_sys-linux.cfg"
)

step "Install build dependencies"
run sudo pacman -S --needed --noconfirm \
    archiso git base-devel squashfs-tools mtools dosfstools libisoburn curl \
    cmake extra-cmake-modules qt6-tools vulkan-headers kwin
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    run sudo pacman -S --needed --noconfirm \
        qt6-base qt6-declarative qt6-svg kdecoration kconfig kconfigwidgets \
        kcoreaddons kcolorscheme kcmutils kcrash kglobalaccel kguiaddons \
        kiconthemes kio kirigami knotifications kpackage kservice ki18n \
        kwindowsystem frameworkintegration libepoxy libdrm libxcb wayland
fi
success "Build dependencies are ready."

step "Refresh local MuliOS package repository"
run bash "$ROOT/scripts/refresh-local-repo.sh" "$PACKAGE_REPO"

step "Prepare build configuration"
printf '%s\n' "$MULIOS_VERSION" > "$ROOT/profile/version"
PACMAN_CONFIG="$BUILD_DIR/pacman.conf"
PACKAGE_REPO="$PACKAGE_REPO" PACMAN_CONFIG="$PACMAN_CONFIG" SOURCE_CONFIG="$ROOT/profile/pacman.conf" python3 - <<'PY'
import os
from pathlib import Path

source = Path(os.environ["SOURCE_CONFIG"]).read_text()
repo = Path(os.environ["PACKAGE_REPO"]).resolve().as_posix()
if "@MULIOS_PACKAGE_REPO@" not in source:
    raise SystemExit("profile/pacman.conf is missing @MULIOS_PACKAGE_REPO@")
Path(os.environ["PACMAN_CONFIG"]).write_text(
    source.replace("@MULIOS_PACKAGE_REPO@", f"file://{repo}")
)
PY
success "Version: $MULIOS_VERSION"
success "Pacman config: $PACMAN_CONFIG"

step "Prepare desktop theme and effects"
THEME_BUILDER="${MULIOS_THEME_BUILDER:-$ROOT/scripts/install-rounded-theme.sh}"
[[ -f "$THEME_BUILDER" ]] || { error "Theme installer not found: $THEME_BUILDER"; exit 1; }
run bash "$THEME_BUILDER"
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    info "Liquid Glass selected; third-party KWin effects are skipped."
else
    run bash "$ROOT/scripts/build-kwin-effects.sh"
fi

step "Validate live image assets"
TASKMANAGER="$ROOT/profile/airootfs/usr/bin/mulios-taskmanager"
[[ -x "$TASKMANAGER" ]] || { error "Rust Task Manager is missing or not executable: $TASKMANAGER"; exit 1; }
install -D -m 0755 "$ROOT/profile/airootfs/usr/share/applications/taskmanager.desktop" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/taskmanager.desktop"
chmod 0755 \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-installer" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-taskmanager" \
    "$TASKMANAGER" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-credits" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-apply-wallpaper" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-wallpaper-autostart" \
    "$ROOT/profile/airootfs/usr/local/bin/fastfetch" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/mulios-installer.desktop" \
    "$ROOT/profile/airootfs/usr/share/applications/mulios-installer.desktop"
success "Required launchers and binaries are present."

step "Run project checks"
run env MULIOS_ROOT="$ROOT" bash "$ROOT/scripts/test.sh"
success "Project checks passed."

step "Apply release metadata"
normalize_version_templates() {
    local file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        sed -E -i 's/(MuliOS )[0-9]{2}\.[0-9]{2}\.[0-9]{2}-[a-z][a-z0-9-]*(\.[0-9]+)?/\1@MULIOS_VERSION@/g' "$file"
    done
}
normalize_version_templates
VERSION_TEMPLATE_BACKUP_DIR="$(mktemp -d "$ROOT/.version-templates.XXXXXX")"
index=0
for file in "${VERSION_TEMPLATE_FILES[@]}"; do
    cp "$file" "$VERSION_TEMPLATE_BACKUP_DIR/$index"
    index=$((index + 1))
    sed -i "s/@MULIOS_VERSION@/$MULIOS_VERSION/g" "$file"
done
cat > "$ROOT/profile/airootfs/etc/os-release" <<EOF
NAME="MuliOS"
PRETTY_NAME="MuliOS Arch $MULIOS_VERSION"
ID=mulios
ID_LIKE=arch
VERSION="$MULIOS_VERSION"
VERSION_ID="$MULIOS_VERSION"
BUILD_ID="$MULIOS_VERSION"
ANSI_COLOR="38;2;0;103;56"
HOME_URL="https://github.com/MuliOS-dev"
IMAGE_ID=MuliOS
IMAGE_VERSION="$MULIOS_VERSION"
MULIOS_RELEASE_BRANCH="$RELEASE_BRANCH"
EOF
success "Release metadata prepared."

step "Build bootable ISO"
run sudo mkarchiso -v -C "$PACMAN_CONFIG" -w "$TEMP" -o "$OUTPUT" "$ROOT/profile"

step "Publish build artifacts"
find "$OUTPUT" -maxdepth 1 -type f -name '*.iso' -printf '%f  %k KB\n'
success "Build artifacts are in $OUTPUT"
\033[34m'; C_CYAN=
else
    C_RESET=''; C_BOLD=''; C_DIM=''; C_BLUE=''; C_CYAN=''
    C_GREEN=''; C_YELLOW=''; C_RED=''
fi

BUILD_ID="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/build-$BUILD_ID.log"
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

STEP=0
CURRENT_STEP="initialization"
VERSION_TEMPLATE_BACKUP_DIR=""
VERSION_TEMPLATE_FILES=()
OUTPUT="$ROOT/output"

log() {
    local color="$1" level="$2"; shift 2
    printf '%s[%s] %s%-7s%s %s\n' "$C_DIM" "$(date '+%H:%M:%S')" "$color" "$level" "$C_RESET" "$*"
}
info()    { log "$C_CYAN" INFO "$*"; }
success() { log "$C_GREEN" OK "$*"; }
error()   { log "$C_RED" ERROR "$*" >&2; }
step() {
    STEP=$((STEP + 1))
    CURRENT_STEP="$*"
    printf '\n%s%s[%02d] %s%s\n' "$C_BOLD" "$C_BLUE" "$STEP" "$CURRENT_STEP" "$C_RESET"
    printf '%s────────────────────────────────────────────────────────%s\n' "$C_DIM" "$C_RESET"
}
run() {
    info "Running: $*"
    "$@"
}
restore_version_templates() {
    [[ -n "$VERSION_TEMPLATE_BACKUP_DIR" && -d "$VERSION_TEMPLATE_BACKUP_DIR" ]] || return 0
    local index=0 file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        cp "$VERSION_TEMPLATE_BACKUP_DIR/$index" "$file"
        index=$((index + 1))
    done
    rm -rf "$VERSION_TEMPLATE_BACKUP_DIR"
    VERSION_TEMPLATE_BACKUP_DIR=""
}
finish() {
    local status=$?
    restore_version_templates
    printf '\n'
    if (( status == 0 )); then
        success "Build completed. ISO output: $OUTPUT"
        success "Build log: $LOG_FILE"
    else
        error "Build failed during: $CURRENT_STEP (exit $status)"
        error "Full log: $LOG_FILE"
    fi
    exit "$status"
}
trap finish EXIT

if [[ ! -f "$ROOT/profile/profiledef.sh" || ! -f "$ROOT/profile/packages.x86_64" ]]; then
    error "Run this script from a valid MuliOS-Arch checkout."
    exit 1
fi
if ! command -v pacman >/dev/null || ! command -v mkarchiso >/dev/null; then
    error "This build must run inside Arch Linux with pacman and archiso installed."
    exit 1
fi
if ! command -v sudo >/dev/null; then
    error "sudo is required to install build dependencies and run mkarchiso."
    exit 1
fi

OUTPUT="$ROOT/output"
TEMP="$ROOT/temp"
PACKAGE_REPO="$ROOT/profile/packages"
BUILD_DIR="$ROOT/.build"
mkdir -p "$OUTPUT" "$TEMP" "$BUILD_DIR"

printf '\n%s%sMuliOS ISO Builder%s\n' "$C_BOLD" "$C_CYAN" "$C_RESET"
info "Build ID: $BUILD_ID"
info "Repository: $ROOT"
info "Log file: $LOG_FILE"
info "Theme: ${MULIOS_THEME_VARIANT:-rounded}"

BUILD_DATE="$(date +%y.%m.%d)"
read -r -p "${C_BOLD}Release channel (stable, beta, indev, indev.xxx): ${C_RESET}" RELEASE_CHANNEL
if [[ ! "$RELEASE_CHANNEL" =~ ^[a-z][a-z0-9-]*([.][a-z0-9-]+)?$ ]]; then
    error "Invalid release channel."
    exit 1
fi
MULIOS_VERSION="$BUILD_DATE-$RELEASE_CHANNEL"
RELEASE_BRANCH="${RELEASE_CHANNEL%%.*}"
case "$RELEASE_BRANCH" in stable|beta|indev) ;; *) RELEASE_BRANCH="unknown" ;; esac

VERSION_TEMPLATE_FILES=(
    "$ROOT/profile/grub/grub.cfg"
    "$ROOT/profile/efiboot/loader/entries/01-archiso-linux.conf"
    "$ROOT/profile/efiboot/loader/entries/02-archiso-speech-linux.conf"
    "$ROOT/profile/syslinux/archiso_sys-linux.cfg"
)

step "Install build dependencies"
run sudo pacman -S --needed --noconfirm \
    archiso git base-devel squashfs-tools mtools dosfstools libisoburn curl \
    cmake extra-cmake-modules qt6-tools vulkan-headers kwin
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    run sudo pacman -S --needed --noconfirm \
        qt6-base qt6-declarative qt6-svg kdecoration kconfig kconfigwidgets \
        kcoreaddons kcolorscheme kcmutils kcrash kglobalaccel kguiaddons \
        kiconthemes kio kirigami knotifications kpackage kservice ki18n \
        kwindowsystem frameworkintegration libepoxy libdrm libxcb wayland
fi
success "Build dependencies are ready."

step "Refresh local MuliOS package repository"
run bash "$ROOT/scripts/refresh-local-repo.sh" "$PACKAGE_REPO"

step "Prepare build configuration"
printf '%s\n' "$MULIOS_VERSION" > "$ROOT/profile/version"
PACMAN_CONFIG="$BUILD_DIR/pacman.conf"
PACKAGE_REPO="$PACKAGE_REPO" PACMAN_CONFIG="$PACMAN_CONFIG" SOURCE_CONFIG="$ROOT/profile/pacman.conf" python3 - <<'PY'
import os
from pathlib import Path

source = Path(os.environ["SOURCE_CONFIG"]).read_text()
repo = Path(os.environ["PACKAGE_REPO"]).resolve().as_posix()
if "@MULIOS_PACKAGE_REPO@" not in source:
    raise SystemExit("profile/pacman.conf is missing @MULIOS_PACKAGE_REPO@")
Path(os.environ["PACMAN_CONFIG"]).write_text(
    source.replace("@MULIOS_PACKAGE_REPO@", f"file://{repo}")
)
PY
success "Version: $MULIOS_VERSION"
success "Pacman config: $PACMAN_CONFIG"

step "Prepare desktop theme and effects"
THEME_BUILDER="${MULIOS_THEME_BUILDER:-$ROOT/scripts/install-rounded-theme.sh}"
[[ -f "$THEME_BUILDER" ]] || { error "Theme installer not found: $THEME_BUILDER"; exit 1; }
run bash "$THEME_BUILDER"
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    info "Liquid Glass selected; third-party KWin effects are skipped."
else
    run bash "$ROOT/scripts/build-kwin-effects.sh"
fi

step "Validate live image assets"
TASKMANAGER="$ROOT/profile/airootfs/usr/bin/mulios-taskmanager"
[[ -x "$TASKMANAGER" ]] || { error "Rust Task Manager is missing or not executable: $TASKMANAGER"; exit 1; }
install -D -m 0755 "$ROOT/profile/airootfs/usr/share/applications/taskmanager.desktop" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/taskmanager.desktop"
chmod 0755 \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-installer" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-taskmanager" \
    "$TASKMANAGER" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-credits" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-apply-wallpaper" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-wallpaper-autostart" \
    "$ROOT/profile/airootfs/usr/local/bin/fastfetch" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/mulios-installer.desktop" \
    "$ROOT/profile/airootfs/usr/share/applications/mulios-installer.desktop"
success "Required launchers and binaries are present."

step "Run project checks"
run env MULIOS_ROOT="$ROOT" bash "$ROOT/scripts/test.sh"
success "Project checks passed."

step "Apply release metadata"
normalize_version_templates() {
    local file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        sed -E -i 's/(MuliOS )[0-9]{2}\.[0-9]{2}\.[0-9]{2}-[a-z][a-z0-9-]*(\.[0-9]+)?/\1@MULIOS_VERSION@/g' "$file"
    done
}
normalize_version_templates
VERSION_TEMPLATE_BACKUP_DIR="$(mktemp -d "$ROOT/.version-templates.XXXXXX")"
index=0
for file in "${VERSION_TEMPLATE_FILES[@]}"; do
    cp "$file" "$VERSION_TEMPLATE_BACKUP_DIR/$index"
    index=$((index + 1))
    sed -i "s/@MULIOS_VERSION@/$MULIOS_VERSION/g" "$file"
done
cat > "$ROOT/profile/airootfs/etc/os-release" <<EOF
NAME="MuliOS"
PRETTY_NAME="MuliOS Arch $MULIOS_VERSION"
ID=mulios
ID_LIKE=arch
VERSION="$MULIOS_VERSION"
VERSION_ID="$MULIOS_VERSION"
BUILD_ID="$MULIOS_VERSION"
ANSI_COLOR="38;2;0;103;56"
HOME_URL="https://github.com/MuliOS-dev"
IMAGE_ID=MuliOS
IMAGE_VERSION="$MULIOS_VERSION"
MULIOS_RELEASE_BRANCH="$RELEASE_BRANCH"
EOF
success "Release metadata prepared."

step "Build bootable ISO"
run sudo mkarchiso -v -C "$PACMAN_CONFIG" -w "$TEMP" -o "$OUTPUT" "$ROOT/profile"

step "Publish build artifacts"
find "$OUTPUT" -maxdepth 1 -type f -name '*.iso' -printf '%f  %k KB\n'
success "Build artifacts are in $OUTPUT"
\033[36m'; C_GREEN=
else
    C_RESET=''; C_BOLD=''; C_DIM=''; C_BLUE=''; C_CYAN=''
    C_GREEN=''; C_YELLOW=''; C_RED=''
fi

BUILD_ID="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/build-$BUILD_ID.log"
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

STEP=0
CURRENT_STEP="initialization"
VERSION_TEMPLATE_BACKUP_DIR=""
VERSION_TEMPLATE_FILES=()
OUTPUT="$ROOT/output"

log() {
    local color="$1" level="$2"; shift 2
    printf '%s[%s] %s%-7s%s %s\n' "$C_DIM" "$(date '+%H:%M:%S')" "$color" "$level" "$C_RESET" "$*"
}
info()    { log "$C_CYAN" INFO "$*"; }
success() { log "$C_GREEN" OK "$*"; }
error()   { log "$C_RED" ERROR "$*" >&2; }
step() {
    STEP=$((STEP + 1))
    CURRENT_STEP="$*"
    printf '\n%s%s[%02d] %s%s\n' "$C_BOLD" "$C_BLUE" "$STEP" "$CURRENT_STEP" "$C_RESET"
    printf '%s────────────────────────────────────────────────────────%s\n' "$C_DIM" "$C_RESET"
}
run() {
    info "Running: $*"
    "$@"
}
restore_version_templates() {
    [[ -n "$VERSION_TEMPLATE_BACKUP_DIR" && -d "$VERSION_TEMPLATE_BACKUP_DIR" ]] || return 0
    local index=0 file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        cp "$VERSION_TEMPLATE_BACKUP_DIR/$index" "$file"
        index=$((index + 1))
    done
    rm -rf "$VERSION_TEMPLATE_BACKUP_DIR"
    VERSION_TEMPLATE_BACKUP_DIR=""
}
finish() {
    local status=$?
    restore_version_templates
    printf '\n'
    if (( status == 0 )); then
        success "Build completed. ISO output: $OUTPUT"
        success "Build log: $LOG_FILE"
    else
        error "Build failed during: $CURRENT_STEP (exit $status)"
        error "Full log: $LOG_FILE"
    fi
    exit "$status"
}
trap finish EXIT

if [[ ! -f "$ROOT/profile/profiledef.sh" || ! -f "$ROOT/profile/packages.x86_64" ]]; then
    error "Run this script from a valid MuliOS-Arch checkout."
    exit 1
fi
if ! command -v pacman >/dev/null || ! command -v mkarchiso >/dev/null; then
    error "This build must run inside Arch Linux with pacman and archiso installed."
    exit 1
fi
if ! command -v sudo >/dev/null; then
    error "sudo is required to install build dependencies and run mkarchiso."
    exit 1
fi

OUTPUT="$ROOT/output"
TEMP="$ROOT/temp"
PACKAGE_REPO="$ROOT/profile/packages"
BUILD_DIR="$ROOT/.build"
mkdir -p "$OUTPUT" "$TEMP" "$BUILD_DIR"

printf '\n%s%sMuliOS ISO Builder%s\n' "$C_BOLD" "$C_CYAN" "$C_RESET"
info "Build ID: $BUILD_ID"
info "Repository: $ROOT"
info "Log file: $LOG_FILE"
info "Theme: ${MULIOS_THEME_VARIANT:-rounded}"

BUILD_DATE="$(date +%y.%m.%d)"
read -r -p "${C_BOLD}Release channel (stable, beta, indev, indev.xxx): ${C_RESET}" RELEASE_CHANNEL
if [[ ! "$RELEASE_CHANNEL" =~ ^[a-z][a-z0-9-]*([.][a-z0-9-]+)?$ ]]; then
    error "Invalid release channel."
    exit 1
fi
MULIOS_VERSION="$BUILD_DATE-$RELEASE_CHANNEL"
RELEASE_BRANCH="${RELEASE_CHANNEL%%.*}"
case "$RELEASE_BRANCH" in stable|beta|indev) ;; *) RELEASE_BRANCH="unknown" ;; esac

VERSION_TEMPLATE_FILES=(
    "$ROOT/profile/grub/grub.cfg"
    "$ROOT/profile/efiboot/loader/entries/01-archiso-linux.conf"
    "$ROOT/profile/efiboot/loader/entries/02-archiso-speech-linux.conf"
    "$ROOT/profile/syslinux/archiso_sys-linux.cfg"
)

step "Install build dependencies"
run sudo pacman -S --needed --noconfirm \
    archiso git base-devel squashfs-tools mtools dosfstools libisoburn curl \
    cmake extra-cmake-modules qt6-tools vulkan-headers kwin
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    run sudo pacman -S --needed --noconfirm \
        qt6-base qt6-declarative qt6-svg kdecoration kconfig kconfigwidgets \
        kcoreaddons kcolorscheme kcmutils kcrash kglobalaccel kguiaddons \
        kiconthemes kio kirigami knotifications kpackage kservice ki18n \
        kwindowsystem frameworkintegration libepoxy libdrm libxcb wayland
fi
success "Build dependencies are ready."

step "Refresh local MuliOS package repository"
run bash "$ROOT/scripts/refresh-local-repo.sh" "$PACKAGE_REPO"

step "Prepare build configuration"
printf '%s\n' "$MULIOS_VERSION" > "$ROOT/profile/version"
PACMAN_CONFIG="$BUILD_DIR/pacman.conf"
PACKAGE_REPO="$PACKAGE_REPO" PACMAN_CONFIG="$PACMAN_CONFIG" SOURCE_CONFIG="$ROOT/profile/pacman.conf" python3 - <<'PY'
import os
from pathlib import Path

source = Path(os.environ["SOURCE_CONFIG"]).read_text()
repo = Path(os.environ["PACKAGE_REPO"]).resolve().as_posix()
if "@MULIOS_PACKAGE_REPO@" not in source:
    raise SystemExit("profile/pacman.conf is missing @MULIOS_PACKAGE_REPO@")
Path(os.environ["PACMAN_CONFIG"]).write_text(
    source.replace("@MULIOS_PACKAGE_REPO@", f"file://{repo}")
)
PY
success "Version: $MULIOS_VERSION"
success "Pacman config: $PACMAN_CONFIG"

step "Prepare desktop theme and effects"
THEME_BUILDER="${MULIOS_THEME_BUILDER:-$ROOT/scripts/install-rounded-theme.sh}"
[[ -f "$THEME_BUILDER" ]] || { error "Theme installer not found: $THEME_BUILDER"; exit 1; }
run bash "$THEME_BUILDER"
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    info "Liquid Glass selected; third-party KWin effects are skipped."
else
    run bash "$ROOT/scripts/build-kwin-effects.sh"
fi

step "Validate live image assets"
TASKMANAGER="$ROOT/profile/airootfs/usr/bin/mulios-taskmanager"
[[ -x "$TASKMANAGER" ]] || { error "Rust Task Manager is missing or not executable: $TASKMANAGER"; exit 1; }
install -D -m 0755 "$ROOT/profile/airootfs/usr/share/applications/taskmanager.desktop" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/taskmanager.desktop"
chmod 0755 \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-installer" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-taskmanager" \
    "$TASKMANAGER" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-credits" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-apply-wallpaper" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-wallpaper-autostart" \
    "$ROOT/profile/airootfs/usr/local/bin/fastfetch" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/mulios-installer.desktop" \
    "$ROOT/profile/airootfs/usr/share/applications/mulios-installer.desktop"
success "Required launchers and binaries are present."

step "Run project checks"
run env MULIOS_ROOT="$ROOT" bash "$ROOT/scripts/test.sh"
success "Project checks passed."

step "Apply release metadata"
normalize_version_templates() {
    local file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        sed -E -i 's/(MuliOS )[0-9]{2}\.[0-9]{2}\.[0-9]{2}-[a-z][a-z0-9-]*(\.[0-9]+)?/\1@MULIOS_VERSION@/g' "$file"
    done
}
normalize_version_templates
VERSION_TEMPLATE_BACKUP_DIR="$(mktemp -d "$ROOT/.version-templates.XXXXXX")"
index=0
for file in "${VERSION_TEMPLATE_FILES[@]}"; do
    cp "$file" "$VERSION_TEMPLATE_BACKUP_DIR/$index"
    index=$((index + 1))
    sed -i "s/@MULIOS_VERSION@/$MULIOS_VERSION/g" "$file"
done
cat > "$ROOT/profile/airootfs/etc/os-release" <<EOF
NAME="MuliOS"
PRETTY_NAME="MuliOS Arch $MULIOS_VERSION"
ID=mulios
ID_LIKE=arch
VERSION="$MULIOS_VERSION"
VERSION_ID="$MULIOS_VERSION"
BUILD_ID="$MULIOS_VERSION"
ANSI_COLOR="38;2;0;103;56"
HOME_URL="https://github.com/MuliOS-dev"
IMAGE_ID=MuliOS
IMAGE_VERSION="$MULIOS_VERSION"
MULIOS_RELEASE_BRANCH="$RELEASE_BRANCH"
EOF
success "Release metadata prepared."

step "Build bootable ISO"
run sudo mkarchiso -v -C "$PACMAN_CONFIG" -w "$TEMP" -o "$OUTPUT" "$ROOT/profile"

step "Publish build artifacts"
find "$OUTPUT" -maxdepth 1 -type f -name '*.iso' -printf '%f  %k KB\n'
success "Build artifacts are in $OUTPUT"
\033[32m'
    C_YELLOW=
else
    C_RESET=''; C_BOLD=''; C_DIM=''; C_BLUE=''; C_CYAN=''
    C_GREEN=''; C_YELLOW=''; C_RED=''
fi

BUILD_ID="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/build-$BUILD_ID.log"
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

STEP=0
CURRENT_STEP="initialization"
VERSION_TEMPLATE_BACKUP_DIR=""
VERSION_TEMPLATE_FILES=()
OUTPUT="$ROOT/output"

log() {
    local color="$1" level="$2"; shift 2
    printf '%s[%s] %s%-7s%s %s\n' "$C_DIM" "$(date '+%H:%M:%S')" "$color" "$level" "$C_RESET" "$*"
}
info()    { log "$C_CYAN" INFO "$*"; }
success() { log "$C_GREEN" OK "$*"; }
error()   { log "$C_RED" ERROR "$*" >&2; }
step() {
    STEP=$((STEP + 1))
    CURRENT_STEP="$*"
    printf '\n%s%s[%02d] %s%s\n' "$C_BOLD" "$C_BLUE" "$STEP" "$CURRENT_STEP" "$C_RESET"
    printf '%s────────────────────────────────────────────────────────%s\n' "$C_DIM" "$C_RESET"
}
run() {
    info "Running: $*"
    "$@"
}
restore_version_templates() {
    [[ -n "$VERSION_TEMPLATE_BACKUP_DIR" && -d "$VERSION_TEMPLATE_BACKUP_DIR" ]] || return 0
    local index=0 file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        cp "$VERSION_TEMPLATE_BACKUP_DIR/$index" "$file"
        index=$((index + 1))
    done
    rm -rf "$VERSION_TEMPLATE_BACKUP_DIR"
    VERSION_TEMPLATE_BACKUP_DIR=""
}
finish() {
    local status=$?
    restore_version_templates
    printf '\n'
    if (( status == 0 )); then
        success "Build completed. ISO output: $OUTPUT"
        success "Build log: $LOG_FILE"
    else
        error "Build failed during: $CURRENT_STEP (exit $status)"
        error "Full log: $LOG_FILE"
    fi
    exit "$status"
}
trap finish EXIT

if [[ ! -f "$ROOT/profile/profiledef.sh" || ! -f "$ROOT/profile/packages.x86_64" ]]; then
    error "Run this script from a valid MuliOS-Arch checkout."
    exit 1
fi
if ! command -v pacman >/dev/null || ! command -v mkarchiso >/dev/null; then
    error "This build must run inside Arch Linux with pacman and archiso installed."
    exit 1
fi
if ! command -v sudo >/dev/null; then
    error "sudo is required to install build dependencies and run mkarchiso."
    exit 1
fi

OUTPUT="$ROOT/output"
TEMP="$ROOT/temp"
PACKAGE_REPO="$ROOT/profile/packages"
BUILD_DIR="$ROOT/.build"
mkdir -p "$OUTPUT" "$TEMP" "$BUILD_DIR"

printf '\n%s%sMuliOS ISO Builder%s\n' "$C_BOLD" "$C_CYAN" "$C_RESET"
info "Build ID: $BUILD_ID"
info "Repository: $ROOT"
info "Log file: $LOG_FILE"
info "Theme: ${MULIOS_THEME_VARIANT:-rounded}"

BUILD_DATE="$(date +%y.%m.%d)"
read -r -p "${C_BOLD}Release channel (stable, beta, indev, indev.xxx): ${C_RESET}" RELEASE_CHANNEL
if [[ ! "$RELEASE_CHANNEL" =~ ^[a-z][a-z0-9-]*([.][a-z0-9-]+)?$ ]]; then
    error "Invalid release channel."
    exit 1
fi
MULIOS_VERSION="$BUILD_DATE-$RELEASE_CHANNEL"
RELEASE_BRANCH="${RELEASE_CHANNEL%%.*}"
case "$RELEASE_BRANCH" in stable|beta|indev) ;; *) RELEASE_BRANCH="unknown" ;; esac

VERSION_TEMPLATE_FILES=(
    "$ROOT/profile/grub/grub.cfg"
    "$ROOT/profile/efiboot/loader/entries/01-archiso-linux.conf"
    "$ROOT/profile/efiboot/loader/entries/02-archiso-speech-linux.conf"
    "$ROOT/profile/syslinux/archiso_sys-linux.cfg"
)

step "Install build dependencies"
run sudo pacman -S --needed --noconfirm \
    archiso git base-devel squashfs-tools mtools dosfstools libisoburn curl \
    cmake extra-cmake-modules qt6-tools vulkan-headers kwin
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    run sudo pacman -S --needed --noconfirm \
        qt6-base qt6-declarative qt6-svg kdecoration kconfig kconfigwidgets \
        kcoreaddons kcolorscheme kcmutils kcrash kglobalaccel kguiaddons \
        kiconthemes kio kirigami knotifications kpackage kservice ki18n \
        kwindowsystem frameworkintegration libepoxy libdrm libxcb wayland
fi
success "Build dependencies are ready."

step "Refresh local MuliOS package repository"
run bash "$ROOT/scripts/refresh-local-repo.sh" "$PACKAGE_REPO"

step "Prepare build configuration"
printf '%s\n' "$MULIOS_VERSION" > "$ROOT/profile/version"
PACMAN_CONFIG="$BUILD_DIR/pacman.conf"
PACKAGE_REPO="$PACKAGE_REPO" PACMAN_CONFIG="$PACMAN_CONFIG" SOURCE_CONFIG="$ROOT/profile/pacman.conf" python3 - <<'PY'
import os
from pathlib import Path

source = Path(os.environ["SOURCE_CONFIG"]).read_text()
repo = Path(os.environ["PACKAGE_REPO"]).resolve().as_posix()
if "@MULIOS_PACKAGE_REPO@" not in source:
    raise SystemExit("profile/pacman.conf is missing @MULIOS_PACKAGE_REPO@")
Path(os.environ["PACMAN_CONFIG"]).write_text(
    source.replace("@MULIOS_PACKAGE_REPO@", f"file://{repo}")
)
PY
success "Version: $MULIOS_VERSION"
success "Pacman config: $PACMAN_CONFIG"

step "Prepare desktop theme and effects"
THEME_BUILDER="${MULIOS_THEME_BUILDER:-$ROOT/scripts/install-rounded-theme.sh}"
[[ -f "$THEME_BUILDER" ]] || { error "Theme installer not found: $THEME_BUILDER"; exit 1; }
run bash "$THEME_BUILDER"
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    info "Liquid Glass selected; third-party KWin effects are skipped."
else
    run bash "$ROOT/scripts/build-kwin-effects.sh"
fi

step "Validate live image assets"
TASKMANAGER="$ROOT/profile/airootfs/usr/bin/mulios-taskmanager"
[[ -x "$TASKMANAGER" ]] || { error "Rust Task Manager is missing or not executable: $TASKMANAGER"; exit 1; }
install -D -m 0755 "$ROOT/profile/airootfs/usr/share/applications/taskmanager.desktop" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/taskmanager.desktop"
chmod 0755 \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-installer" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-taskmanager" \
    "$TASKMANAGER" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-credits" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-apply-wallpaper" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-wallpaper-autostart" \
    "$ROOT/profile/airootfs/usr/local/bin/fastfetch" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/mulios-installer.desktop" \
    "$ROOT/profile/airootfs/usr/share/applications/mulios-installer.desktop"
success "Required launchers and binaries are present."

step "Run project checks"
run env MULIOS_ROOT="$ROOT" bash "$ROOT/scripts/test.sh"
success "Project checks passed."

step "Apply release metadata"
normalize_version_templates() {
    local file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        sed -E -i 's/(MuliOS )[0-9]{2}\.[0-9]{2}\.[0-9]{2}-[a-z][a-z0-9-]*(\.[0-9]+)?/\1@MULIOS_VERSION@/g' "$file"
    done
}
normalize_version_templates
VERSION_TEMPLATE_BACKUP_DIR="$(mktemp -d "$ROOT/.version-templates.XXXXXX")"
index=0
for file in "${VERSION_TEMPLATE_FILES[@]}"; do
    cp "$file" "$VERSION_TEMPLATE_BACKUP_DIR/$index"
    index=$((index + 1))
    sed -i "s/@MULIOS_VERSION@/$MULIOS_VERSION/g" "$file"
done
cat > "$ROOT/profile/airootfs/etc/os-release" <<EOF
NAME="MuliOS"
PRETTY_NAME="MuliOS Arch $MULIOS_VERSION"
ID=mulios
ID_LIKE=arch
VERSION="$MULIOS_VERSION"
VERSION_ID="$MULIOS_VERSION"
BUILD_ID="$MULIOS_VERSION"
ANSI_COLOR="38;2;0;103;56"
HOME_URL="https://github.com/MuliOS-dev"
IMAGE_ID=MuliOS
IMAGE_VERSION="$MULIOS_VERSION"
MULIOS_RELEASE_BRANCH="$RELEASE_BRANCH"
EOF
success "Release metadata prepared."

step "Build bootable ISO"
run sudo mkarchiso -v -C "$PACMAN_CONFIG" -w "$TEMP" -o "$OUTPUT" "$ROOT/profile"

step "Publish build artifacts"
find "$OUTPUT" -maxdepth 1 -type f -name '*.iso' -printf '%f  %k KB\n'
success "Build artifacts are in $OUTPUT"
\033[33m'; C_RED=
else
    C_RESET=''; C_BOLD=''; C_DIM=''; C_BLUE=''; C_CYAN=''
    C_GREEN=''; C_YELLOW=''; C_RED=''
fi

BUILD_ID="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/build-$BUILD_ID.log"
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

STEP=0
CURRENT_STEP="initialization"
VERSION_TEMPLATE_BACKUP_DIR=""
VERSION_TEMPLATE_FILES=()
OUTPUT="$ROOT/output"

log() {
    local color="$1" level="$2"; shift 2
    printf '%s[%s] %s%-7s%s %s\n' "$C_DIM" "$(date '+%H:%M:%S')" "$color" "$level" "$C_RESET" "$*"
}
info()    { log "$C_CYAN" INFO "$*"; }
success() { log "$C_GREEN" OK "$*"; }
error()   { log "$C_RED" ERROR "$*" >&2; }
step() {
    STEP=$((STEP + 1))
    CURRENT_STEP="$*"
    printf '\n%s%s[%02d] %s%s\n' "$C_BOLD" "$C_BLUE" "$STEP" "$CURRENT_STEP" "$C_RESET"
    printf '%s────────────────────────────────────────────────────────%s\n' "$C_DIM" "$C_RESET"
}
run() {
    info "Running: $*"
    "$@"
}
restore_version_templates() {
    [[ -n "$VERSION_TEMPLATE_BACKUP_DIR" && -d "$VERSION_TEMPLATE_BACKUP_DIR" ]] || return 0
    local index=0 file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        cp "$VERSION_TEMPLATE_BACKUP_DIR/$index" "$file"
        index=$((index + 1))
    done
    rm -rf "$VERSION_TEMPLATE_BACKUP_DIR"
    VERSION_TEMPLATE_BACKUP_DIR=""
}
finish() {
    local status=$?
    restore_version_templates
    printf '\n'
    if (( status == 0 )); then
        success "Build completed. ISO output: $OUTPUT"
        success "Build log: $LOG_FILE"
    else
        error "Build failed during: $CURRENT_STEP (exit $status)"
        error "Full log: $LOG_FILE"
    fi
    exit "$status"
}
trap finish EXIT

if [[ ! -f "$ROOT/profile/profiledef.sh" || ! -f "$ROOT/profile/packages.x86_64" ]]; then
    error "Run this script from a valid MuliOS-Arch checkout."
    exit 1
fi
if ! command -v pacman >/dev/null || ! command -v mkarchiso >/dev/null; then
    error "This build must run inside Arch Linux with pacman and archiso installed."
    exit 1
fi
if ! command -v sudo >/dev/null; then
    error "sudo is required to install build dependencies and run mkarchiso."
    exit 1
fi

OUTPUT="$ROOT/output"
TEMP="$ROOT/temp"
PACKAGE_REPO="$ROOT/profile/packages"
BUILD_DIR="$ROOT/.build"
mkdir -p "$OUTPUT" "$TEMP" "$BUILD_DIR"

printf '\n%s%sMuliOS ISO Builder%s\n' "$C_BOLD" "$C_CYAN" "$C_RESET"
info "Build ID: $BUILD_ID"
info "Repository: $ROOT"
info "Log file: $LOG_FILE"
info "Theme: ${MULIOS_THEME_VARIANT:-rounded}"

BUILD_DATE="$(date +%y.%m.%d)"
read -r -p "${C_BOLD}Release channel (stable, beta, indev, indev.xxx): ${C_RESET}" RELEASE_CHANNEL
if [[ ! "$RELEASE_CHANNEL" =~ ^[a-z][a-z0-9-]*([.][a-z0-9-]+)?$ ]]; then
    error "Invalid release channel."
    exit 1
fi
MULIOS_VERSION="$BUILD_DATE-$RELEASE_CHANNEL"
RELEASE_BRANCH="${RELEASE_CHANNEL%%.*}"
case "$RELEASE_BRANCH" in stable|beta|indev) ;; *) RELEASE_BRANCH="unknown" ;; esac

VERSION_TEMPLATE_FILES=(
    "$ROOT/profile/grub/grub.cfg"
    "$ROOT/profile/efiboot/loader/entries/01-archiso-linux.conf"
    "$ROOT/profile/efiboot/loader/entries/02-archiso-speech-linux.conf"
    "$ROOT/profile/syslinux/archiso_sys-linux.cfg"
)

step "Install build dependencies"
run sudo pacman -S --needed --noconfirm \
    archiso git base-devel squashfs-tools mtools dosfstools libisoburn curl \
    cmake extra-cmake-modules qt6-tools vulkan-headers kwin
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    run sudo pacman -S --needed --noconfirm \
        qt6-base qt6-declarative qt6-svg kdecoration kconfig kconfigwidgets \
        kcoreaddons kcolorscheme kcmutils kcrash kglobalaccel kguiaddons \
        kiconthemes kio kirigami knotifications kpackage kservice ki18n \
        kwindowsystem frameworkintegration libepoxy libdrm libxcb wayland
fi
success "Build dependencies are ready."

step "Refresh local MuliOS package repository"
run bash "$ROOT/scripts/refresh-local-repo.sh" "$PACKAGE_REPO"

step "Prepare build configuration"
printf '%s\n' "$MULIOS_VERSION" > "$ROOT/profile/version"
PACMAN_CONFIG="$BUILD_DIR/pacman.conf"
PACKAGE_REPO="$PACKAGE_REPO" PACMAN_CONFIG="$PACMAN_CONFIG" SOURCE_CONFIG="$ROOT/profile/pacman.conf" python3 - <<'PY'
import os
from pathlib import Path

source = Path(os.environ["SOURCE_CONFIG"]).read_text()
repo = Path(os.environ["PACKAGE_REPO"]).resolve().as_posix()
if "@MULIOS_PACKAGE_REPO@" not in source:
    raise SystemExit("profile/pacman.conf is missing @MULIOS_PACKAGE_REPO@")
Path(os.environ["PACMAN_CONFIG"]).write_text(
    source.replace("@MULIOS_PACKAGE_REPO@", f"file://{repo}")
)
PY
success "Version: $MULIOS_VERSION"
success "Pacman config: $PACMAN_CONFIG"

step "Prepare desktop theme and effects"
THEME_BUILDER="${MULIOS_THEME_BUILDER:-$ROOT/scripts/install-rounded-theme.sh}"
[[ -f "$THEME_BUILDER" ]] || { error "Theme installer not found: $THEME_BUILDER"; exit 1; }
run bash "$THEME_BUILDER"
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    info "Liquid Glass selected; third-party KWin effects are skipped."
else
    run bash "$ROOT/scripts/build-kwin-effects.sh"
fi

step "Validate live image assets"
TASKMANAGER="$ROOT/profile/airootfs/usr/bin/mulios-taskmanager"
[[ -x "$TASKMANAGER" ]] || { error "Rust Task Manager is missing or not executable: $TASKMANAGER"; exit 1; }
install -D -m 0755 "$ROOT/profile/airootfs/usr/share/applications/taskmanager.desktop" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/taskmanager.desktop"
chmod 0755 \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-installer" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-taskmanager" \
    "$TASKMANAGER" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-credits" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-apply-wallpaper" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-wallpaper-autostart" \
    "$ROOT/profile/airootfs/usr/local/bin/fastfetch" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/mulios-installer.desktop" \
    "$ROOT/profile/airootfs/usr/share/applications/mulios-installer.desktop"
success "Required launchers and binaries are present."

step "Run project checks"
run env MULIOS_ROOT="$ROOT" bash "$ROOT/scripts/test.sh"
success "Project checks passed."

step "Apply release metadata"
normalize_version_templates() {
    local file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        sed -E -i 's/(MuliOS )[0-9]{2}\.[0-9]{2}\.[0-9]{2}-[a-z][a-z0-9-]*(\.[0-9]+)?/\1@MULIOS_VERSION@/g' "$file"
    done
}
normalize_version_templates
VERSION_TEMPLATE_BACKUP_DIR="$(mktemp -d "$ROOT/.version-templates.XXXXXX")"
index=0
for file in "${VERSION_TEMPLATE_FILES[@]}"; do
    cp "$file" "$VERSION_TEMPLATE_BACKUP_DIR/$index"
    index=$((index + 1))
    sed -i "s/@MULIOS_VERSION@/$MULIOS_VERSION/g" "$file"
done
cat > "$ROOT/profile/airootfs/etc/os-release" <<EOF
NAME="MuliOS"
PRETTY_NAME="MuliOS Arch $MULIOS_VERSION"
ID=mulios
ID_LIKE=arch
VERSION="$MULIOS_VERSION"
VERSION_ID="$MULIOS_VERSION"
BUILD_ID="$MULIOS_VERSION"
ANSI_COLOR="38;2;0;103;56"
HOME_URL="https://github.com/MuliOS-dev"
IMAGE_ID=MuliOS
IMAGE_VERSION="$MULIOS_VERSION"
MULIOS_RELEASE_BRANCH="$RELEASE_BRANCH"
EOF
success "Release metadata prepared."

step "Build bootable ISO"
run sudo mkarchiso -v -C "$PACMAN_CONFIG" -w "$TEMP" -o "$OUTPUT" "$ROOT/profile"

step "Publish build artifacts"
find "$OUTPUT" -maxdepth 1 -type f -name '*.iso' -printf '%f  %k KB\n'
success "Build artifacts are in $OUTPUT"
\033[31m'; C_MAGENTA=
else
    C_RESET=''; C_BOLD=''; C_DIM=''; C_BLUE=''; C_CYAN=''
    C_GREEN=''; C_YELLOW=''; C_RED=''
fi

BUILD_ID="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/build-$BUILD_ID.log"
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

STEP=0
CURRENT_STEP="initialization"
VERSION_TEMPLATE_BACKUP_DIR=""
VERSION_TEMPLATE_FILES=()
OUTPUT="$ROOT/output"

log() {
    local color="$1" level="$2"; shift 2
    printf '%s[%s] %s%-7s%s %s\n' "$C_DIM" "$(date '+%H:%M:%S')" "$color" "$level" "$C_RESET" "$*"
}
info()    { log "$C_CYAN" INFO "$*"; }
success() { log "$C_GREEN" OK "$*"; }
error()   { log "$C_RED" ERROR "$*" >&2; }
step() {
    STEP=$((STEP + 1))
    CURRENT_STEP="$*"
    printf '\n%s%s[%02d] %s%s\n' "$C_BOLD" "$C_BLUE" "$STEP" "$CURRENT_STEP" "$C_RESET"
    printf '%s────────────────────────────────────────────────────────%s\n' "$C_DIM" "$C_RESET"
}
run() {
    info "Running: $*"
    "$@"
}
restore_version_templates() {
    [[ -n "$VERSION_TEMPLATE_BACKUP_DIR" && -d "$VERSION_TEMPLATE_BACKUP_DIR" ]] || return 0
    local index=0 file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        cp "$VERSION_TEMPLATE_BACKUP_DIR/$index" "$file"
        index=$((index + 1))
    done
    rm -rf "$VERSION_TEMPLATE_BACKUP_DIR"
    VERSION_TEMPLATE_BACKUP_DIR=""
}
finish() {
    local status=$?
    restore_version_templates
    printf '\n'
    if (( status == 0 )); then
        success "Build completed. ISO output: $OUTPUT"
        success "Build log: $LOG_FILE"
    else
        error "Build failed during: $CURRENT_STEP (exit $status)"
        error "Full log: $LOG_FILE"
    fi
    exit "$status"
}
trap finish EXIT

if [[ ! -f "$ROOT/profile/profiledef.sh" || ! -f "$ROOT/profile/packages.x86_64" ]]; then
    error "Run this script from a valid MuliOS-Arch checkout."
    exit 1
fi
if ! command -v pacman >/dev/null || ! command -v mkarchiso >/dev/null; then
    error "This build must run inside Arch Linux with pacman and archiso installed."
    exit 1
fi
if ! command -v sudo >/dev/null; then
    error "sudo is required to install build dependencies and run mkarchiso."
    exit 1
fi

OUTPUT="$ROOT/output"
TEMP="$ROOT/temp"
PACKAGE_REPO="$ROOT/profile/packages"
BUILD_DIR="$ROOT/.build"
mkdir -p "$OUTPUT" "$TEMP" "$BUILD_DIR"

printf '\n%s%sMuliOS ISO Builder%s\n' "$C_BOLD" "$C_CYAN" "$C_RESET"
info "Build ID: $BUILD_ID"
info "Repository: $ROOT"
info "Log file: $LOG_FILE"
info "Theme: ${MULIOS_THEME_VARIANT:-rounded}"

BUILD_DATE="$(date +%y.%m.%d)"
read -r -p "${C_BOLD}Release channel (stable, beta, indev, indev.xxx): ${C_RESET}" RELEASE_CHANNEL
if [[ ! "$RELEASE_CHANNEL" =~ ^[a-z][a-z0-9-]*([.][a-z0-9-]+)?$ ]]; then
    error "Invalid release channel."
    exit 1
fi
MULIOS_VERSION="$BUILD_DATE-$RELEASE_CHANNEL"
RELEASE_BRANCH="${RELEASE_CHANNEL%%.*}"
case "$RELEASE_BRANCH" in stable|beta|indev) ;; *) RELEASE_BRANCH="unknown" ;; esac

VERSION_TEMPLATE_FILES=(
    "$ROOT/profile/grub/grub.cfg"
    "$ROOT/profile/efiboot/loader/entries/01-archiso-linux.conf"
    "$ROOT/profile/efiboot/loader/entries/02-archiso-speech-linux.conf"
    "$ROOT/profile/syslinux/archiso_sys-linux.cfg"
)

step "Install build dependencies"
run sudo pacman -S --needed --noconfirm \
    archiso git base-devel squashfs-tools mtools dosfstools libisoburn curl \
    cmake extra-cmake-modules qt6-tools vulkan-headers kwin
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    run sudo pacman -S --needed --noconfirm \
        qt6-base qt6-declarative qt6-svg kdecoration kconfig kconfigwidgets \
        kcoreaddons kcolorscheme kcmutils kcrash kglobalaccel kguiaddons \
        kiconthemes kio kirigami knotifications kpackage kservice ki18n \
        kwindowsystem frameworkintegration libepoxy libdrm libxcb wayland
fi
success "Build dependencies are ready."

step "Refresh local MuliOS package repository"
run bash "$ROOT/scripts/refresh-local-repo.sh" "$PACKAGE_REPO"

step "Prepare build configuration"
printf '%s\n' "$MULIOS_VERSION" > "$ROOT/profile/version"
PACMAN_CONFIG="$BUILD_DIR/pacman.conf"
PACKAGE_REPO="$PACKAGE_REPO" PACMAN_CONFIG="$PACMAN_CONFIG" SOURCE_CONFIG="$ROOT/profile/pacman.conf" python3 - <<'PY'
import os
from pathlib import Path

source = Path(os.environ["SOURCE_CONFIG"]).read_text()
repo = Path(os.environ["PACKAGE_REPO"]).resolve().as_posix()
if "@MULIOS_PACKAGE_REPO@" not in source:
    raise SystemExit("profile/pacman.conf is missing @MULIOS_PACKAGE_REPO@")
Path(os.environ["PACMAN_CONFIG"]).write_text(
    source.replace("@MULIOS_PACKAGE_REPO@", f"file://{repo}")
)
PY
success "Version: $MULIOS_VERSION"
success "Pacman config: $PACMAN_CONFIG"

step "Prepare desktop theme and effects"
THEME_BUILDER="${MULIOS_THEME_BUILDER:-$ROOT/scripts/install-rounded-theme.sh}"
[[ -f "$THEME_BUILDER" ]] || { error "Theme installer not found: $THEME_BUILDER"; exit 1; }
run bash "$THEME_BUILDER"
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    info "Liquid Glass selected; third-party KWin effects are skipped."
else
    run bash "$ROOT/scripts/build-kwin-effects.sh"
fi

step "Validate live image assets"
TASKMANAGER="$ROOT/profile/airootfs/usr/bin/mulios-taskmanager"
[[ -x "$TASKMANAGER" ]] || { error "Rust Task Manager is missing or not executable: $TASKMANAGER"; exit 1; }
install -D -m 0755 "$ROOT/profile/airootfs/usr/share/applications/taskmanager.desktop" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/taskmanager.desktop"
chmod 0755 \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-installer" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-taskmanager" \
    "$TASKMANAGER" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-credits" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-apply-wallpaper" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-wallpaper-autostart" \
    "$ROOT/profile/airootfs/usr/local/bin/fastfetch" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/mulios-installer.desktop" \
    "$ROOT/profile/airootfs/usr/share/applications/mulios-installer.desktop"
success "Required launchers and binaries are present."

step "Run project checks"
run env MULIOS_ROOT="$ROOT" bash "$ROOT/scripts/test.sh"
success "Project checks passed."

step "Apply release metadata"
normalize_version_templates() {
    local file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        sed -E -i 's/(MuliOS )[0-9]{2}\.[0-9]{2}\.[0-9]{2}-[a-z][a-z0-9-]*(\.[0-9]+)?/\1@MULIOS_VERSION@/g' "$file"
    done
}
normalize_version_templates
VERSION_TEMPLATE_BACKUP_DIR="$(mktemp -d "$ROOT/.version-templates.XXXXXX")"
index=0
for file in "${VERSION_TEMPLATE_FILES[@]}"; do
    cp "$file" "$VERSION_TEMPLATE_BACKUP_DIR/$index"
    index=$((index + 1))
    sed -i "s/@MULIOS_VERSION@/$MULIOS_VERSION/g" "$file"
done
cat > "$ROOT/profile/airootfs/etc/os-release" <<EOF
NAME="MuliOS"
PRETTY_NAME="MuliOS Arch $MULIOS_VERSION"
ID=mulios
ID_LIKE=arch
VERSION="$MULIOS_VERSION"
VERSION_ID="$MULIOS_VERSION"
BUILD_ID="$MULIOS_VERSION"
ANSI_COLOR="38;2;0;103;56"
HOME_URL="https://github.com/MuliOS-dev"
IMAGE_ID=MuliOS
IMAGE_VERSION="$MULIOS_VERSION"
MULIOS_RELEASE_BRANCH="$RELEASE_BRANCH"
EOF
success "Release metadata prepared."

step "Build bootable ISO"
run sudo mkarchiso -v -C "$PACMAN_CONFIG" -w "$TEMP" -o "$OUTPUT" "$ROOT/profile"

step "Publish build artifacts"
find "$OUTPUT" -maxdepth 1 -type f -name '*.iso' -printf '%f  %k KB\n'
success "Build artifacts are in $OUTPUT"
\033[35m'
else
    C_RESET=''; C_BOLD=''; C_DIM=''; C_BLUE=''; C_CYAN=''
    C_GREEN=''; C_YELLOW=''; C_RED=''
fi

BUILD_ID="$(date +%Y%m%d-%H%M%S)"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/build-$BUILD_ID.log"
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

STEP=0
CURRENT_STEP="initialization"
VERSION_TEMPLATE_BACKUP_DIR=""
VERSION_TEMPLATE_FILES=()
OUTPUT="$ROOT/output"

log() {
    local color="$1" level="$2"; shift 2
    printf '%s[%s] %s%-7s%s %s\n' "$C_DIM" "$(date '+%H:%M:%S')" "$color" "$level" "$C_RESET" "$*"
}
info()    { log "$C_CYAN" INFO "$*"; }
success() { log "$C_GREEN" OK "$*"; }
error()   { log "$C_RED" ERROR "$*" >&2; }
step() {
    STEP=$((STEP + 1))
    CURRENT_STEP="$*"
    printf '\n%s%s[%02d] %s%s\n' "$C_BOLD" "$C_BLUE" "$STEP" "$CURRENT_STEP" "$C_RESET"
    printf '%s────────────────────────────────────────────────────────%s\n' "$C_DIM" "$C_RESET"
}
run() {
    info "Running: $*"
    "$@"
}
restore_version_templates() {
    [[ -n "$VERSION_TEMPLATE_BACKUP_DIR" && -d "$VERSION_TEMPLATE_BACKUP_DIR" ]] || return 0
    local index=0 file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        cp "$VERSION_TEMPLATE_BACKUP_DIR/$index" "$file"
        index=$((index + 1))
    done
    rm -rf "$VERSION_TEMPLATE_BACKUP_DIR"
    VERSION_TEMPLATE_BACKUP_DIR=""
}
finish() {
    local status=$?
    restore_version_templates
    printf '\n'
    if (( status == 0 )); then
        success "Build completed. ISO output: $OUTPUT"
        success "Build log: $LOG_FILE"
    else
        error "Build failed during: $CURRENT_STEP (exit $status)"
        error "Full log: $LOG_FILE"
    fi
    exit "$status"
}
trap finish EXIT

if [[ ! -f "$ROOT/profile/profiledef.sh" || ! -f "$ROOT/profile/packages.x86_64" ]]; then
    error "Run this script from a valid MuliOS-Arch checkout."
    exit 1
fi
if ! command -v pacman >/dev/null || ! command -v mkarchiso >/dev/null; then
    error "This build must run inside Arch Linux with pacman and archiso installed."
    exit 1
fi
if ! command -v sudo >/dev/null; then
    error "sudo is required to install build dependencies and run mkarchiso."
    exit 1
fi

OUTPUT="$ROOT/output"
TEMP="$ROOT/temp"
PACKAGE_REPO="$ROOT/profile/packages"
BUILD_DIR="$ROOT/.build"
mkdir -p "$OUTPUT" "$TEMP" "$BUILD_DIR"

printf '\n%s%sMuliOS ISO Builder%s\n' "$C_BOLD" "$C_CYAN" "$C_RESET"
info "Build ID: $BUILD_ID"
info "Repository: $ROOT"
info "Log file: $LOG_FILE"
info "Theme: ${MULIOS_THEME_VARIANT:-rounded}"

BUILD_DATE="$(date +%y.%m.%d)"
read -r -p "${C_BOLD}Release channel (stable, beta, indev, indev.xxx): ${C_RESET}" RELEASE_CHANNEL
if [[ ! "$RELEASE_CHANNEL" =~ ^[a-z][a-z0-9-]*([.][a-z0-9-]+)?$ ]]; then
    error "Invalid release channel."
    exit 1
fi
MULIOS_VERSION="$BUILD_DATE-$RELEASE_CHANNEL"
RELEASE_BRANCH="${RELEASE_CHANNEL%%.*}"
case "$RELEASE_BRANCH" in stable|beta|indev) ;; *) RELEASE_BRANCH="unknown" ;; esac

VERSION_TEMPLATE_FILES=(
    "$ROOT/profile/grub/grub.cfg"
    "$ROOT/profile/efiboot/loader/entries/01-archiso-linux.conf"
    "$ROOT/profile/efiboot/loader/entries/02-archiso-speech-linux.conf"
    "$ROOT/profile/syslinux/archiso_sys-linux.cfg"
)

step "Install build dependencies"
run sudo pacman -S --needed --noconfirm \
    archiso git base-devel squashfs-tools mtools dosfstools libisoburn curl \
    cmake extra-cmake-modules qt6-tools vulkan-headers kwin
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    run sudo pacman -S --needed --noconfirm \
        qt6-base qt6-declarative qt6-svg kdecoration kconfig kconfigwidgets \
        kcoreaddons kcolorscheme kcmutils kcrash kglobalaccel kguiaddons \
        kiconthemes kio kirigami knotifications kpackage kservice ki18n \
        kwindowsystem frameworkintegration libepoxy libdrm libxcb wayland
fi
success "Build dependencies are ready."

step "Refresh local MuliOS package repository"
run bash "$ROOT/scripts/refresh-local-repo.sh" "$PACKAGE_REPO"

step "Prepare build configuration"
printf '%s\n' "$MULIOS_VERSION" > "$ROOT/profile/version"
PACMAN_CONFIG="$BUILD_DIR/pacman.conf"
PACKAGE_REPO="$PACKAGE_REPO" PACMAN_CONFIG="$PACMAN_CONFIG" SOURCE_CONFIG="$ROOT/profile/pacman.conf" python3 - <<'PY'
import os
from pathlib import Path

source = Path(os.environ["SOURCE_CONFIG"]).read_text()
repo = Path(os.environ["PACKAGE_REPO"]).resolve().as_posix()
if "@MULIOS_PACKAGE_REPO@" not in source:
    raise SystemExit("profile/pacman.conf is missing @MULIOS_PACKAGE_REPO@")
Path(os.environ["PACMAN_CONFIG"]).write_text(
    source.replace("@MULIOS_PACKAGE_REPO@", f"file://{repo}")
)
PY
success "Version: $MULIOS_VERSION"
success "Pacman config: $PACMAN_CONFIG"

step "Prepare desktop theme and effects"
THEME_BUILDER="${MULIOS_THEME_BUILDER:-$ROOT/scripts/install-rounded-theme.sh}"
[[ -f "$THEME_BUILDER" ]] || { error "Theme installer not found: $THEME_BUILDER"; exit 1; }
run bash "$THEME_BUILDER"
if [[ "${MULIOS_THEME_VARIANT:-rounded}" == "liquid-glass" ]]; then
    info "Liquid Glass selected; third-party KWin effects are skipped."
else
    run bash "$ROOT/scripts/build-kwin-effects.sh"
fi

step "Validate live image assets"
TASKMANAGER="$ROOT/profile/airootfs/usr/bin/mulios-taskmanager"
[[ -x "$TASKMANAGER" ]] || { error "Rust Task Manager is missing or not executable: $TASKMANAGER"; exit 1; }
install -D -m 0755 "$ROOT/profile/airootfs/usr/share/applications/taskmanager.desktop" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/taskmanager.desktop"
chmod 0755 \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-installer" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-taskmanager" \
    "$TASKMANAGER" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-credits" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-apply-wallpaper" \
    "$ROOT/profile/airootfs/usr/local/bin/mulios-wallpaper-autostart" \
    "$ROOT/profile/airootfs/usr/local/bin/fastfetch" \
    "$ROOT/profile/airootfs/etc/skel/Desktop/mulios-installer.desktop" \
    "$ROOT/profile/airootfs/usr/share/applications/mulios-installer.desktop"
success "Required launchers and binaries are present."

step "Run project checks"
run env MULIOS_ROOT="$ROOT" bash "$ROOT/scripts/test.sh"
success "Project checks passed."

step "Apply release metadata"
normalize_version_templates() {
    local file
    for file in "${VERSION_TEMPLATE_FILES[@]}"; do
        sed -E -i 's/(MuliOS )[0-9]{2}\.[0-9]{2}\.[0-9]{2}-[a-z][a-z0-9-]*(\.[0-9]+)?/\1@MULIOS_VERSION@/g' "$file"
    done
}
normalize_version_templates
VERSION_TEMPLATE_BACKUP_DIR="$(mktemp -d "$ROOT/.version-templates.XXXXXX")"
index=0
for file in "${VERSION_TEMPLATE_FILES[@]}"; do
    cp "$file" "$VERSION_TEMPLATE_BACKUP_DIR/$index"
    index=$((index + 1))
    sed -i "s/@MULIOS_VERSION@/$MULIOS_VERSION/g" "$file"
done
cat > "$ROOT/profile/airootfs/etc/os-release" <<EOF
NAME="MuliOS"
PRETTY_NAME="MuliOS Arch $MULIOS_VERSION"
ID=mulios
ID_LIKE=arch
VERSION="$MULIOS_VERSION"
VERSION_ID="$MULIOS_VERSION"
BUILD_ID="$MULIOS_VERSION"
ANSI_COLOR="38;2;0;103;56"
HOME_URL="https://github.com/MuliOS-dev"
IMAGE_ID=MuliOS
IMAGE_VERSION="$MULIOS_VERSION"
MULIOS_RELEASE_BRANCH="$RELEASE_BRANCH"
EOF
success "Release metadata prepared."

step "Build bootable ISO"
run sudo mkarchiso -v -C "$PACMAN_CONFIG" -w "$TEMP" -o "$OUTPUT" "$ROOT/profile"

step "Publish build artifacts"
find "$OUTPUT" -maxdepth 1 -type f -name '*.iso' -printf '%f  %k KB\n'
success "Build artifacts are in $OUTPUT"
