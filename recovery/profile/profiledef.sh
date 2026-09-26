#!/usr/bin/env bash
# shellcheck disable=SC2034

version="$(cat version)"

iso_name="MuliRecovery"
iso_label="MULIRECOVERY_$version"
iso_publisher="MuliOS Project"
iso_application="MuliOS offline recovery environment"
iso_version="$version"

install_dir="mulirecovery"

buildmodes=('iso')

bootmodes=(
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

file_permissions=(
  ["/usr/local/bin/mulirecovery"]="0:0:755"
  ["/sbin/init"]="0:0:755"
)
