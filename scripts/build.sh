#!/usr/bin/env bash
# Builds the MuliOS ISO. The profile/pacman.conf.in and boot menu templates are
# rendered into a staged copy of the profile (.build/profile); mkarchiso only
# ever sees that copy.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$ROOT/profile"
STAGE="$ROOT/.build/profile"
WORK="$ROOT/temp"
OUTPUT="$ROOT/output"
export MULIOS_THEME_VARIANT="${MULIOS_THEME_VARIANT:-rounded}"
THEME_BUILDER="${MULIOS_THEME_BUILDER:-$ROOT/scripts/install-rounded-theme.sh}"

die() {
    echo "[ERROR]: $*" >&2
    exit 1
}

info() {
    echo "[INFO]: $*"
}

read_version() {
    local channel
    read -r -p "Enter release channel (e.g. stable, beta, indev, indev.2): " channel
    [[ "$channel" =~ ^[a-z][a-z0-9-]*(\.[0-9]+)?$ ]] ||
        die "invalid channel '$channel'. Use lowercase letters, digits and hyphens, optionally followed by .NUMBER"
    VERSION="$(date +%y.%m.%d)-$channel"
    case "${channel%%.*}" in
        stable|beta|indev) RELEASE_BRANCH="${channel%%.*}" ;;
        *) RELEASE_BRANCH="unknown" ;;
    esac
}

install_dependencies() {
    command -v pacman >/dev/null || die "not in an Arch Linux environment"
    local packages=(
        archiso git base-devel squashfs-tools mtools dosfstools libisoburn curl python
        cmake extra-cmake-modules qt6-tools vulkan-headers kwin
    )
    if [[ "$MULIOS_THEME_VARIANT" == "liquid-glass" ]]; then
        packages+=(
            qt6-base qt6-declarative qt6-svg kdecoration kconfig kconfigwidgets
            kcoreaddons kcolorscheme kcmutils kcrash kglobalaccel kguiaddons
            kiconthemes kio kirigami knotifications kpackage kservice ki18n
            kwindowsystem frameworkintegration libepoxy libdrm libxcb wayland
        )
    fi
    info "installing dependencies"
    sudo pacman -S --needed --noconfirm "${packages[@]}"
}

# mkarchiso skips steps already marked done in its work directory, including
# the pacman.conf copy. A leftover work directory therefore replays old config.
remove_work_directory() {
    [[ -e "$WORK" ]] || return 0
    if findmnt -rn -o TARGET | grep -q "^$WORK/"; then
        die "filesystems are still mounted under $WORK. Reboot or unmount them, then retry"
    fi
    info "removing previous work directory $WORK"
    sudo rm -rf -- "$WORK"
}

build_assets() {
    bash "$THEME_BUILDER"
    if [[ "$MULIOS_THEME_VARIANT" == "liquid-glass" ]]; then
        info "skipping third-party KWin effects for Liquid Glass safe boot"
    else
        bash "$ROOT/scripts/build-kwin-effects.sh"
    fi
}

stage_profile() {
    info "staging profile in $STAGE"
    rm -rf -- "$STAGE"
    mkdir -p "$(dirname -- "$STAGE")"
    cp -a "$PROFILE" "$STAGE"

    sed "s|@MULIOS_PACKAGE_REPO@|file://$PROFILE/packages|" \
        "$STAGE/pacman.conf.in" > "$STAGE/pacman.conf"

    sed -i "s/@MULIOS_VERSION@/$VERSION/g" \
        "$STAGE/grub/grub.cfg" \
        "$STAGE/efiboot/loader/entries/01-archiso-linux.conf" \
        "$STAGE/efiboot/loader/entries/02-archiso-speech-linux.conf" \
        "$STAGE/syslinux/archiso_sys-linux.cfg"

    # Trusted Task Manager shortcut on the live user's desktop.
    install -D -m 0755 \
        "$STAGE/airootfs/usr/share/applications/taskmanager.desktop" \
        "$STAGE/airootfs/etc/skel/Desktop/taskmanager.desktop"

    cat > "$STAGE/airootfs/etc/os-release" <<OSRELEASE
NAME="MuliOS"
PRETTY_NAME="MuliOS Arch $VERSION"
ID=mulios
ID_LIKE=arch
VERSION="$VERSION"
VERSION_ID="$VERSION"
BUILD_ID="$VERSION"
ANSI_COLOR="38;2;0;103;56"
HOME_URL="https://github.com/MuliOS-dev"
IMAGE_ID=MuliOS
IMAGE_VERSION="$VERSION"
MULIOS_RELEASE_BRANCH="$RELEASE_BRANCH"
OSRELEASE
}

main() {
    # The theme installers use paths relative to the repository root.
    cd "$ROOT"
    [[ -f "$THEME_BUILDER" ]] || die "theme installer not found: $THEME_BUILDER"

    read_version
    info "building MuliOS version $VERSION"

    install_dependencies
    remove_work_directory
    bash "$ROOT/scripts/refresh-local-repo.sh" "$PROFILE/packages"
    build_assets
    printf '%s\n' "$VERSION" > "$PROFILE/version"
    stage_profile

    mkdir -p "$OUTPUT"
    sudo mkarchiso -v -w "$WORK" -o "$OUTPUT" "$STAGE"

    info "build complete, the ISO is in $OUTPUT"
    ls -lh "$OUTPUT"
}

main
