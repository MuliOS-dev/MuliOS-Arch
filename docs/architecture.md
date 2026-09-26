# Architecture

This document describes the technical architecture of MuliOS-Arch: how the Arch Linux base, ArchISO profile, desktop configuration, installer, and MuliOS-specific tooling fit together to produce a bootable, installable operating system image.

## Overview

MuliOS-Arch is not a fork of Arch Linux. It is a **custom ArchISO profile and configuration layer** built on top of standard Arch Linux packages, assembled using the official `archiso` tooling. At a high level, the build process takes stock Arch Linux packages, layers MuliOS configuration and branding on top, and packages the result into a bootable ISO with an integrated graphical installer.

```
┌─────────────────────────────────────────────┐
│                Arch Linux Base               │
│        (official packages & repositories)    │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────┐
│              ArchISO Profile                 │
│   profile/ (profiledef.sh, packages.x86_64,  │
│   pacman.conf, airootfs/, boot configs)      │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────┐
│         MuliOS Configuration Layer            │
│   configs/ (kde, plymouth, fastfetch,        │
│   calamares) + packages/ (mulios-tools,       │
│   mulios-installer)                          │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────┐
│              Bootable MuliOS ISO             │
│    (live environment)  │
└─────────────────────────────────────────────┘
```

## Arch Linux Base

MuliOS-Arch relies entirely on official Arch Linux packages as its foundation. No packages are forked or patched at the distribution level; instead, `pacman.conf` (in `profile/`) defines which repositories and mirrors are used to pull packages during the build. This keeps MuliOS-Arch aligned with upstream Arch Linux and simplifies maintenance, since system-level updates and security fixes come directly from Arch's repositories.

## ArchISO Profile

The `profile/` directory is a standard [ArchISO](https://wiki.archlinux.org/title/Archiso) profile, built using `mkarchiso`. Its components are:

- **`profiledef.sh`** — defines ISO metadata and build behavior, such as the ISO name, version string, compression method, and file permissions applied during the build.
- **`packages.x86_64`** — a flat list of package names installed into the live root filesystem. This includes both standard Arch packages and MuliOS packages produced from `packages/`.
- **`pacman.conf`** — the pacman configuration used specifically during the ISO build, controlling which repositories (official and any MuliOS-specific ones) are consulted.
- **`airootfs/`** — an overlay directory copied directly onto the live filesystem after package installation. This is where system-wide configuration files, default user settings, and branding assets are placed so that they exist on the live and installed system.
- **`efiboot/`, `grub/`, `syslinux/`** — bootloader configuration for UEFI and legacy BIOS boot, respectively. These control how the ISO presents boot menus and starts the live environment across different firmware types.

## KDE Configuration

MuliOS-Arch uses **KDE Plasma** as its desktop environment. Configuration specific to MuliOS's desktop experience lives in `configs/kde/`, and is applied to the live environment via the `airootfs/` overlay (and/or installed onto the target system through the installer, depending on how the build wires these files together). This includes default settings and desktop behavior intended to give MuliOS a consistent look and feel out of the box.

Two supporting components round out the desktop experience:

- **Plymouth** (`configs/plymouth/`) — controls the boot splash screen shown while the system starts, before the desktop environment loads.
- **Fastfetch** (`configs/fastfetch/`) — configures the system information summary displayed in the terminal, typically used to show branding and system details at a glance.

## MuliOS Installer

MuliOS-Arch uses **Calamares** as its graphical installer, configured in `configs/calamares/`. This configuration defines the installer's modules, branding, and installation sequence, allowing users to install MuliOS onto persistent storage from the live environment. Calamares configuration in this repository is specific to MuliOS-Arch's installation flow and branding; it does not modify Calamares itself, only its configuration.

Where installer behavior requires MuliOS-specific logic beyond what Calamares provides out of the box, this is supplied through `packages/mulios-installer/`.

## MuliOS Tools

`packages/mulios-tools/` contains command-line utilities authored specifically for MuliOS. These tools are built as packages and included in the live environment via `packages.x86_64`, giving users and administrators MuliOS-specific functionality that is not part of stock Arch Linux.

## Custom Branding

Branding (logos, color schemes, wallpapers, and related assets) is applied across multiple layers of the system rather than in a single location:

- Boot-time branding is defined through **Plymouth** (`configs/plymouth/`) and the bootloader configuration (`grub/`, `syslinux/`, `efiboot/`).
- Desktop branding is defined through **KDE configuration** (`configs/kde/`).
- Installer branding is defined through **Calamares configuration** (`configs/calamares/`).
- Terminal branding is defined through **Fastfetch** (`configs/fastfetch/`).

This layered approach means branding changes are made at the component responsible for that part of the user experience, rather than in a single central branding module.

## Build-Time Assembly

Putting it together, `scripts/build.sh` orchestrates the process:

1. `mkarchiso` reads `profile/profiledef.sh` and `profile/pacman.conf` to determine how and from where to install packages.
2. Packages listed in `profile/packages.x86_64` — including standard Arch packages and MuliOS packages from `packages/` — are installed into a working root filesystem.
3. `profile/airootfs/` is overlaid on top of that root filesystem, applying MuliOS-specific configuration and files.
4. Bootloader configuration from `efiboot/`, `grub/`, and `syslinux/` is applied so the resulting image boots correctly on both UEFI and legacy BIOS systems.
5. The result is packaged into a bootable `.iso` file containing the live environment and the configured MuliOS Installer.

See [`building.md`](building.md) for the practical steps to run this process, and [`development.md`](development.md) for how these pieces map onto day-to-day development work.
