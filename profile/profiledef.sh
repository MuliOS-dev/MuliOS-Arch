#!/usr/bin/env bash
# shellcheck disable=SC2034

# MuliOS Version
version="$(cat version)"

iso_name="MuliOS"
iso_label="MULIOS_${version}"
iso_publisher="MuliOS Project"
iso_application="MuliOS Arch Linux Live ISO"
iso_version="${version}"

install_dir="arch"

buildmodes=('iso')

bootmodes=(
  'bios.syslinux'
  'uefi.systemd-boot'
)

pacman_conf="pacman.conf"

airootfs_image_type="squashfs"

airootfs_image_tool_options=(
  '-comp' 'xz'
  '-Xbcj' 'x86'
  '-b' '1M'
  '-Xdict-size' '100%'
)

bootstrap_tarball_compression=(
  'zstd'
  '-c'
  '-T0'
  '--auto-threads=logical'
  '--long'
  '-19'
)

file_permissions=(
  ["/etc/shadow"]="0:0:400"

  ["/usr/local/bin/mupdate"]="0:0:755"
  ["/usr/local/bin/livecd-sound"]="0:0:755"
  ["/usr/share/backgrounds/mulios"]="0:0:755"
)