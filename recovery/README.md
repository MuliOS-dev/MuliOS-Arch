# MuliRecovery

MuliRecovery is the small offline recovery environment used by MUpdate.

It is a console-only Archiso environment. It locates the installed MuliOS
system, unlocks encrypted roots when necessary, reads the persistent MUpdate
transaction, verifies the staged OTA ISO, merges the new MuliOS root while
preserving setup directories, restores backups, rebuilds initramfs and GRUB,
and reboots.

Build:

```bash
cd /root/MuliOS-Arch/recovery
./build.sh
```

The ISO is written to:

```
recovery/output/MuliRecovery-1.0.0-x86_64.iso
```

Install the built ISO for MUpdate:

```bash
sudo mkdir -p /var/lib/mupdate/recovery/iso
sudo cp recovery/output/MuliRecovery-1.0.0-x86_64.iso /var/lib/mupdate/recovery/iso/
```
