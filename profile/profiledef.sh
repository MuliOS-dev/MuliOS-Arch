# MuliOS Developpement Team
#
# Notice To Developers. iso_label and iso_version "_version" is a placeholder. replace with your own version's name
# make sure it is easy to remember, and is based of the version you are using.
#

iso_name="MuliOS"
iso_label="MuliOS_version"
iso_publisher="MuliOS"
iso_application="MuliOS Arch Linux"
iso_version="version"
install_dir="arch"
buildmodes=('iso')

bootmodes=(
  'uefi-x64.systemd-boot.esp-mode'
  'bios.syslinux.mbr'
  'bios.syslinux.eltorito'
)

arch="x86_64"
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
file_permissions=(
  ["/etc/shadow"]="0:0:400"
)
