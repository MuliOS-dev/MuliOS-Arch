#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# MuliOS Build System
# ==============================================================================
# Builds a customized Ubuntu/Xubuntu-based ISO from a pinned base ISO.
#
# Design goals:
# - reproducible Git-based build recipe
# - no Cubic project directory dependency
# - safe chroot provisioning
# - defensive mount cleanup
# - no eval-based xorriso parsing
# - signed/checksummed release artifacts
#
# Expected usage inside a privileged Linux container:
#
#   BASE_ISO_URL="https://..." \
#   BASE_ISO_SHA256="..." \
#   MULIOS_BUILD_TYPE="dev" \
#   ./scripts/build.sh
#
# For release compression:
#
#   MULIOS_BUILD_TYPE="release" ./scripts/build.sh
#
# ==============================================================================

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BUILD_DIR="${BASE_DIR}/build_workspace"
ISO_DIR="${BUILD_DIR}/iso_structure"
CHROOT_DIR="${BUILD_DIR}/chroot"
OUT_DIR="${BASE_DIR}/dist"

BASE_ISO_URL="${BASE_ISO_URL:-}"
BASE_ISO_SHA256="${BASE_ISO_SHA256:-}"
BASE_ISO="${BUILD_DIR}/base.iso"

MULIOS_VERSION="${MULIOS_VERSION:-26.04}"
MULIOS_ISO_LABEL="${MULIOS_ISO_LABEL:-MuliOS_26}"
MULIOS_OUTPUT_NAME="${MULIOS_OUTPUT_NAME:-MuliOS-${MULIOS_VERSION}-desktop-amd64.iso}"
OUTPUT_ISO="${OUT_DIR}/${MULIOS_OUTPUT_NAME}"

BUILD_TYPE="${MULIOS_BUILD_TYPE:-dev}"

PACKAGES_INSTALL="${BASE_DIR}/packages/packages.list"
PACKAGES_REMOVE="${BASE_DIR}/packages/packages-remove.txt"
SETUP_TWEAKS="${BASE_DIR}/scripts/setup-tweaks.sh"
XORRISO_ARGS_FILE="${BASE_DIR}/config/xorriso-args.txt"

ACTIVE_SQUASHFS_PATH_FILE="${BUILD_DIR}/active-squashfs.path"

log() {
  printf '\n==> %s\n' "$*"
}

warn() {
  printf '\nWARNING: %s\n' "$*" >&2
}

die() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

# ------------------------------------------------------------------------------
# Safety checks
# ------------------------------------------------------------------------------

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    die "This build must run as root inside a privileged Linux container."
  fi
}

require_linux() {
  if [ "$(uname -s)" != "Linux" ]; then
    die "This script must run on Linux. On macOS, run it inside a Linux Docker container or CI."
  fi
}

require_amd64_build_host() {
  local arch
  arch="$(uname -m)"

  case "$arch" in
    x86_64|amd64)
      ;;
    *)
      warn "Build host architecture is '$arch'."
      warn "If the target ISO is amd64, chroot provisioning may fail without qemu-user-static/binfmt."
      ;;
  esac
}

require_tools() {
  local tools=(
    awk
    bash
    chroot
    curl
    file
    find
    grep
    mksquashfs
    mount
    mountpoint
    rsync
    sed
    sha256sum
    sort
    stat
    tee
    umount
    unsquashfs
    xargs
    xorriso
  )

  for tool in "${tools[@]}"; do
    command -v "$tool" >/dev/null 2>&1 || die "Missing required tool: $tool"
  done
}

validate_inputs() {
  [ -n "$BASE_ISO_URL" ] || die "BASE_ISO_URL is not set."
  [ -n "$BASE_ISO_SHA256" ] || die "BASE_ISO_SHA256 is not set."

  [ -f "$SETUP_TWEAKS" ] || die "Missing setup tweaks script: $SETUP_TWEAKS"

  if [ ! -f "$PACKAGES_INSTALL" ]; then
    warn "Missing packages install file: $PACKAGES_INSTALL"
    warn "Continuing without extra package install list."
  fi

  if [ ! -f "$PACKAGES_REMOVE" ]; then
    warn "Missing packages remove file: $PACKAGES_REMOVE"
    warn "Continuing without package removal list."
  fi

  if [ ! -f "$XORRISO_ARGS_FILE" ]; then
    warn "Missing approved xorriso args file: $XORRISO_ARGS_FILE"
    warn "The script will still prepare the build workspace and write xorriso reports, but final ISO creation will stop until this file is added."
  fi
}

acquire_lock() {
  mkdir -p "$BUILD_DIR"
  exec 9>"$BUILD_DIR/.build.lock"

  if ! flock -n 9; then
    die "Another build is already running in $BUILD_DIR"
  fi
}

# ------------------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------------------

restore_resolv_conf() {
  if [ -e "$CHROOT_DIR/etc/resolv.conf.mulios.bak" ] || [ -L "$CHROOT_DIR/etc/resolv.conf.mulios.bak" ]; then
    rm -f "$CHROOT_DIR/etc/resolv.conf" || true
    mv "$CHROOT_DIR/etc/resolv.conf.mulios.bak" "$CHROOT_DIR/etc/resolv.conf" || true
  else
    rm -f "$CHROOT_DIR/etc/resolv.conf" || true
  fi
}

cleanup_mounts() {
  local mounts=(
    "$CHROOT_DIR/run"
    "$CHROOT_DIR/dev/shm"
    "$CHROOT_DIR/dev/pts"
    "$CHROOT_DIR/dev"
    "$CHROOT_DIR/proc"
    "$CHROOT_DIR/sys"
  )

  for mnt in "${mounts[@]}"; do
    if mountpoint -q "$mnt"; then
      umount -lf "$mnt" || true
    fi
  done
}

cleanup() {
  log "Cleaning up build mounts and temporary files"

  cleanup_mounts
  restore_resolv_conf

  rm -f "$CHROOT_DIR/usr/sbin/policy-rc.d" 2>/dev/null || true
}

trap cleanup EXIT INT TERM ERR

# ------------------------------------------------------------------------------
# Base ISO
# ------------------------------------------------------------------------------

fetch_base_iso() {
  mkdir -p "$BUILD_DIR" "$OUT_DIR"

  if [ ! -f "$BASE_ISO" ]; then
    log "Downloading base ISO"
    curl -L "$BASE_ISO_URL" -o "$BASE_ISO"
  else
    log "Base ISO already exists, reusing: $BASE_ISO"
  fi

  log "Verifying base ISO SHA-256"
  echo "$BASE_ISO_SHA256  $BASE_ISO" | sha256sum -c -
}

extract_iso() {
  log "Extracting base ISO structure"

  rm -rf "$ISO_DIR"
  mkdir -p "$ISO_DIR"

  xorriso -osirrox on \
    -indev "$BASE_ISO" \
    -extract / "$ISO_DIR"

  chmod -R u+w "$ISO_DIR"
}

detect_primary_squashfs() {
  log "Detecting primary SquashFS"

  local squashfs
  squashfs="$(
    find "$ISO_DIR/casper" -maxdepth 1 -type f -name "*.squashfs" -printf '%s %p\n' \
      | sort -nr \
      | head -n1 \
      | cut -d' ' -f2-
  )"

  [ -n "$squashfs" ] || die "No SquashFS file found in $ISO_DIR/casper"

  echo "$squashfs" > "$ACTIVE_SQUASHFS_PATH_FILE"

  log "Selected SquashFS: $squashfs"
}

extract_squashfs() {
  log "Extracting SquashFS root filesystem"

  rm -rf "$CHROOT_DIR"

  local squashfs
  squashfs="$(cat "$ACTIVE_SQUASHFS_PATH_FILE")"

  unsquashfs -d "$CHROOT_DIR" "$squashfs"
}

# ------------------------------------------------------------------------------
# Chroot preparation
# ------------------------------------------------------------------------------

prepare_chroot_mounts() {
  log "Preparing chroot pseudo-filesystems"

  mkdir -p \
    "$CHROOT_DIR/dev" \
    "$CHROOT_DIR/dev/pts" \
    "$CHROOT_DIR/dev/shm" \
    "$CHROOT_DIR/proc" \
    "$CHROOT_DIR/sys" \
    "$CHROOT_DIR/run"

  mount --bind /dev "$CHROOT_DIR/dev"
  mount --bind /dev/pts "$CHROOT_DIR/dev/pts"
  mount --bind /dev/shm "$CHROOT_DIR/dev/shm"
  mount -t proc proc "$CHROOT_DIR/proc"
  mount -t sysfs sys "$CHROOT_DIR/sys"

  # Practical for Ubuntu package configuration in containerized builds.
  # Do not bind efivars. The build must never touch host firmware variables.
  mount --bind /run "$CHROOT_DIR/run"
}

prepare_chroot_dns() {
  log "Preparing DNS inside chroot"

  if [ -e "$CHROOT_DIR/etc/resolv.conf" ] || [ -L "$CHROOT_DIR/etc/resolv.conf" ]; then
    cp -a "$CHROOT_DIR/etc/resolv.conf" "$CHROOT_DIR/etc/resolv.conf.mulios.bak"
  fi

  cp /etc/resolv.conf "$CHROOT_DIR/etc/resolv.conf"
}

install_policy_rc_d() {
  log "Installing policy-rc.d to prevent services from starting inside chroot"

  cat > "$CHROOT_DIR/usr/sbin/policy-rc.d" <<'EOF'
#!/bin/sh
exit 101
EOF

  chmod +x "$CHROOT_DIR/usr/sbin/policy-rc.d"
}

copy_build_inputs() {
  log "Copying package lists and tweak scripts into chroot"

  mkdir -p "$CHROOT_DIR/tmp/mulios-build"

  if [ -f "$PACKAGES_INSTALL" ]; then
    cp "$PACKAGES_INSTALL" "$CHROOT_DIR/tmp/mulios-build/packages-install.txt"
  fi

  if [ -f "$PACKAGES_REMOVE" ]; then
    cp "$PACKAGES_REMOVE" "$CHROOT_DIR/tmp/mulios-build/packages-remove.txt"
  fi

  cp "$SETUP_TWEAKS" "$CHROOT_DIR/tmp/mulios-build/setup-tweaks.sh"
  chmod +x "$CHROOT_DIR/tmp/mulios-build/setup-tweaks.sh"
}

# ------------------------------------------------------------------------------
# Chroot provisioning
# ------------------------------------------------------------------------------

provision_chroot() {
  log "Provisioning chroot"

  chroot "$CHROOT_DIR" /usr/bin/env -i \
    HOME=/root \
    TERM="${TERM:-xterm}" \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    DEBIAN_FRONTEND=noninteractive \
    /bin/bash -euxo pipefail <<'CHROOT_EOF'
apt-get update

if [ -f /tmp/mulios-build/packages-remove.txt ]; then
  grep -vE '^\s*(#|$)' /tmp/mulios-build/packages-remove.txt \
    | xargs -r apt-get purge -y
fi

if [ -f /tmp/mulios-build/packages-install.txt ]; then
  grep -vE '^\s*(#|$)' /tmp/mulios-build/packages-install.txt \
    | xargs -r apt-get install -y \
        -o Dpkg::Options::="--force-confold"
fi

/tmp/mulios-build/setup-tweaks.sh

apt-get autoremove -y --purge
apt-get clean

rm -rf /var/lib/apt/lists/*
rm -f /var/cache/apt/pkgcache.bin /var/cache/apt/srcpkgcache.bin
rm -rf /tmp/* /var/tmp/*

find /var/log -type f -exec truncate -s 0 {} \;

truncate -s 0 /etc/machine-id || true
rm -f /var/lib/dbus/machine-id || true
ln -sf /etc/machine-id /var/lib/dbus/machine-id || true

rm -f /usr/sbin/policy-rc.d
CHROOT_EOF
}

# ------------------------------------------------------------------------------
# Systemd service policy by direct rootfs manipulation
# ------------------------------------------------------------------------------

mask_unit_in_rootfs() {
  local unit="$1"

  mkdir -p "$CHROOT_DIR/etc/systemd/system"

  # Remove enablement symlinks pointing to the unit.
  find "$CHROOT_DIR/etc/systemd/system" -type l \
    \( -name "$unit" -o -lname "*/$unit" \) \
    -delete 2>/dev/null || true

  # Mask unit.
  ln -sfn /dev/null "$CHROOT_DIR/etc/systemd/system/$unit"
}

apply_service_policy() {
  log "Applying public-build service policy"

  local units_to_mask=(
    whoopsie.service
    whoopsie.path

    apport.service
    apport-autoreport.timer
    apport-autoreport.path
    apport-forward.socket

    avahi-daemon.service
    avahi-daemon.socket

    cups-browsed.service

    motd-news.timer
    ua-timer.timer
    update-notifier-motd.timer
  )

  for unit in "${units_to_mask[@]}"; do
    mask_unit_in_rootfs "$unit"
  done
}

# ------------------------------------------------------------------------------
# Static audit gates
# ------------------------------------------------------------------------------

audit_no_human_users() {
  log "Audit: checking for preinstalled human users"

  if awk -F: '$3 >= 1000 && $3 < 65534 {print}' "$CHROOT_DIR/etc/passwd" | grep .; then
    die "Preinstalled human users found in rootfs."
  fi
}

audit_root_password_locked() {
  log "Audit: checking root password state"

  if awk -F: '$1=="root" && $2 ~ /^\$/ {print}' "$CHROOT_DIR/etc/shadow" | grep .; then
    die "Root has an active password hash."
  fi
}

audit_sudoers() {
  log "Audit: checking sudoers"

  if grep -RInE 'NOPASSWD:[[:space:]]*ALL|ALL[[:space:]]+ALL=\(ALL\)[[:space:]]+NOPASSWD' \
    "$CHROOT_DIR/etc/sudoers" "$CHROOT_DIR/etc/sudoers.d" 2>/dev/null | grep .; then
    die "Dangerous NOPASSWD sudo rule found."
  fi
}

audit_ssh_backdoors() {
  log "Audit: checking SSH authorized_keys"

  if find "$CHROOT_DIR" -path "*/.ssh/authorized_keys" -print | grep .; then
    die "SSH authorized_keys found in image."
  fi
}

audit_private_keys_high_risk_paths() {
  log "Audit: checking private keys in high-risk paths"

  if grep -RIlE "BEGIN (RSA|OPENSSH|DSA|EC|PRIVATE) KEY" \
    "$CHROOT_DIR/etc" \
    "$CHROOT_DIR/root" \
    "$CHROOT_DIR/home" \
    "$CHROOT_DIR/opt" \
    "$CHROOT_DIR/usr/local" 2>/dev/null | grep .; then
    die "Private key material found in high-risk paths."
  fi
}

audit_forbidden_packages() {
  log "Audit: checking forbidden packages"

  local forbidden_regex='^(openssh-server|telnet|inetutils-telnet|ftp|tnftp)$'

  if chroot "$CHROOT_DIR" dpkg-query -W -f='${Package}\n' \
    | grep -E "$forbidden_regex" \
    | grep .; then
    die "Forbidden package found in rootfs package database."
  fi
}

audit_boot_flags() {
  log "Audit: checking dangerous boot flags"

  if grep -RInE 'mitigations=off|apparmor=0|nospectre|selinux=0|init=/bin/bash' \
    "$ISO_DIR/boot" "$ISO_DIR/EFI" 2>/dev/null | grep .; then
    die "Dangerous kernel boot flag found."
  fi
}

audit_branding_leaks() {
  log "Audit: checking obvious Xubuntu branding leaks in boot files"

  if grep -RInE 'Try or Install Xubuntu|Xubuntu \(safe graphics\)' \
    "$ISO_DIR/boot" "$ISO_DIR/EFI" 2>/dev/null | grep .; then
    die "Xubuntu branding leak found in boot configuration."
  fi
}

run_static_audits() {
  log "Running static audit gates"

  audit_no_human_users
  audit_root_password_locked
  audit_sudoers
  audit_ssh_backdoors
  audit_private_keys_high_risk_paths
  audit_forbidden_packages
  audit_boot_flags
  audit_branding_leaks
}

# ------------------------------------------------------------------------------
# Manifest, SquashFS, checksums
# ------------------------------------------------------------------------------

update_manifest() {
  log "Updating package manifest"

  local target_manifest=""

  if [ -f "$ISO_DIR/casper/minimal.manifest" ]; then
    target_manifest="$ISO_DIR/casper/minimal.manifest"
  elif [ -f "$ISO_DIR/casper/filesystem.manifest" ]; then
    target_manifest="$ISO_DIR/casper/filesystem.manifest"
  else
    warn "No known manifest file found. Creating casper/filesystem.manifest"
    target_manifest="$ISO_DIR/casper/filesystem.manifest"
  fi

  chroot "$CHROOT_DIR" dpkg-query -W --showformat='${Package} ${Version}\n' \
    > "$target_manifest"

  log "Updated manifest: $target_manifest"
}

update_filesystem_size() {
  log "Updating filesystem.size"

  du -sx --block-size=1 "$CHROOT_DIR" | cut -f1 \
    > "$ISO_DIR/casper/filesystem.size"
}

rebuild_squashfs() {
  log "Rebuilding SquashFS"

  local squashfs
  squashfs="$(cat "$ACTIVE_SQUASHFS_PATH_FILE")"

  rm -f "$squashfs"

  case "$BUILD_TYPE" in
    release)
      log "Using release compression: xz + max dictionary"
      mksquashfs "$CHROOT_DIR" "$squashfs" \
        -noappend \
        -comp xz \
        -b 1048576 \
        -Xbcj x86 \
        -Xdict-size 100%
      ;;
    dev)
      log "Using dev compression: zstd"
      mksquashfs "$CHROOT_DIR" "$squashfs" \
        -noappend \
        -comp zstd \
        -Xcompression-level 6
      ;;
    *)
      die "Unknown MULIOS_BUILD_TYPE: $BUILD_TYPE. Use 'dev' or 'release'."
      ;;
  esac
}

update_internal_md5sum() {
  log "Updating internal md5sum.txt"

  (
    cd "$ISO_DIR"

    find . -type f \
      ! -name "md5sum.txt" \
      ! -path "./isolinux/boot.cat" \
      ! -path "./boot.catalog" \
      -print0 \
      | sort -z \
      | xargs -0 md5sum > md5sum.txt
  )
}

# ------------------------------------------------------------------------------
# ISO build
# ------------------------------------------------------------------------------

write_xorriso_report() {
  log "Writing original xorriso El Torito report"

  xorriso -indev "$BASE_ISO" -report_el_torito as_mkisofs \
    > "$BUILD_DIR/xorriso-boot-options.txt"

  xorriso -indev "$BASE_ISO" -report_el_torito plain \
    > "$BUILD_DIR/xorriso-boot-plain.txt"

  log "Reports written:"
  log "$BUILD_DIR/xorriso-boot-options.txt"
  log "$BUILD_DIR/xorriso-boot-plain.txt"
}

load_xorriso_args() {
  local args_file="$1"

  [ -f "$args_file" ] || die "Missing xorriso args file: $args_file"

  mapfile -t XORRISO_ARGS < <(
    grep -vE '^\s*(#|$)' "$args_file"
  )
}

build_iso() {
  log "Generating final bootable ISO via approved xorriso args"

  mkdir -p "$OUT_DIR"

  write_xorriso_report

  if [ ! -f "$XORRISO_ARGS_FILE" ]; then
    die "Missing approved xorriso args file: $XORRISO_ARGS_FILE

The workspace and boot reports were generated successfully.
Review these files:

  $BUILD_DIR/xorriso-boot-options.txt
  $BUILD_DIR/xorriso-boot-plain.txt

Then create:

  $XORRISO_ARGS_FILE

Use one xorriso argument per line. Do not use eval/sed-generated boot commands in the official build."
  fi

  load_xorriso_args "$XORRISO_ARGS_FILE"

  xorriso -as mkisofs \
    "${XORRISO_ARGS[@]}" \
    -V "$MULIOS_ISO_LABEL" \
    -o "$OUTPUT_ISO" \
    "$ISO_DIR"

  log "Built ISO: $OUTPUT_ISO"
}

validate_output_iso() {
  log "Validating output ISO boot metadata"

  [ -f "$OUTPUT_ISO" ] || die "Output ISO not found: $OUTPUT_ISO"

  xorriso -indev "$OUTPUT_ISO" -report_el_torito plain \
    > "$OUT_DIR/${MULIOS_OUTPUT_NAME}.eltorito.txt"

  xorriso -indev "$OUTPUT_ISO" -report_system_area plain \
    > "$OUT_DIR/${MULIOS_OUTPUT_NAME}.system-area.txt"

  file "$OUTPUT_ISO" | tee "$OUT_DIR/${MULIOS_OUTPUT_NAME}.file.txt"
}

release_checksums() {
  log "Generating release SHA-256 checksum"

  (
    cd "$OUT_DIR"
    sha256sum "$MULIOS_OUTPUT_NAME" > "$MULIOS_OUTPUT_NAME.sha256"
  )

  log "Checksum written: $OUTPUT_ISO.sha256"

  if command -v gpg >/dev/null 2>&1; then
    warn "GPG detected. Signature is not generated automatically by default."
    warn "Run manually in release environment:"
    warn "gpg --detach-sign --armor '$OUTPUT_ISO.sha256'"
  fi
}

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

main() {
  log "Starting MuliOS Build System"
  log "Build type: $BUILD_TYPE"

  require_linux
  require_root
  require_amd64_build_host
  require_tools
  validate_inputs
  acquire_lock

  fetch_base_iso
  extract_iso
  detect_primary_squashfs
  extract_squashfs

  prepare_chroot_mounts
  prepare_chroot_dns
  install_policy_rc_d
  copy_build_inputs
  provision_chroot

  apply_service_policy

  run_static_audits

  # Important: unmount before rebuilding SquashFS.
  cleanup
  trap - EXIT INT TERM ERR

  update_manifest
  update_filesystem_size
  rebuild_squashfs
  update_internal_md5sum

  build_iso
  validate_output_iso
  release_checksums

  log "MuliOS Build Completed Successfully"
}

main "$@"