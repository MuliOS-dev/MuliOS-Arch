# MuliOS Native Installer

The MuliOS Installer is a native PySide6 installer for the MuliOS Arch ISO.

It performs the installation directly against the selected disk. It does not
use Calamares or Archinstall.

## Structure

- `main.py` — installer window and navigation
- `theme.py` — dark, translucent frosted-glass UI
- `config/settings.py` — MuliOS profiles and fixed KDE/GRUB choices
- `pages/` — installer wizard pages
- `backend/native_installer_worker.py` — disk, filesystem, package, user,
  initramfs and bootloader installation
- `utils/validators.py` — hostname, username and password validation

## Installation flow

Welcome -> Language -> Keyboard -> Timezone -> Network -> Disk -> Partitioning
-> Bootloader -> Account -> Desktop -> Packages -> Profile -> Advanced
-> Summary -> Install -> Finished

MuliOS installs KDE Plasma and GRUB. These are fixed choices and are not
presented as alternative desktop environments or bootloaders.

## Password handling

A password mismatch is still an error.

An empty or short user password is accepted with a warning. If no user
password is selected, the installed wheel account is configured for
passwordless sudo so the account remains usable.

## Pacman

The installer initializes and populates the target Arch keyring before using
pacman. The keyring is initialized explicitly instead of testing an empty
keyring with `pacman-key --list-keys`, which can return exit code 1.

The live ISO also includes `archlinux-keyring`.

## Logging

Installation output is shown in the installer and written to:

```
/var/log/mulios/install.log
```

## Testing

Run the installer from a MuliOS live session:

```bash
sudo python3 /opt/mulios-installer/main.py
```
