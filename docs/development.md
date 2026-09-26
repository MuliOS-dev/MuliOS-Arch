# Development Guide

This document explains how the MuliOS-Arch repository is organized, how its components interact, and how the day-to-day development workflow operates. It is intended for developers who are building, modifying, or extending MuliOS-Arch.

## Repository Structure

```
MuliOS-Arch/
├── profile/            # ArchISO profile used to build the ISO
│   ├── profiledef.sh   # ISO build configuration (name, version, compression, etc.)
│   ├── packages.x86_64 # List of packages installed into the live environment
│   ├── pacman.conf     # Pacman configuration used during the build
│   ├── airootfs/       # Files copied directly into the live root filesystem
│   ├── efiboot/        # UEFI boot configuration
│   ├── grub/           # GRUB bootloader configuration
│   └── syslinux/       # BIOS (legacy) bootloader configuration
│
├── packages/            # MuliOS-authored packages
│   ├── mulios-installer/ # Installer-related package(s)
│   └── mulios-tools/     # MuliOS-specific command-line tools and utilities
│
├── scripts/             # Build and maintenance automation
│   ├── build.sh         # Builds the ISO using mkarchiso
│   ├── prepare.sh       # Prepares the build environment
│   └── test.sh          # Runs tests / cleanup routines against a build
│
└── docs/                 # Project documentation (this folder)
```

## How the Components Interact

MuliOS-Arch assembles a working Arch Linux live/install image by combining several independent pieces at build time:

1. **`profile/`** defines the base of the ISO. `profiledef.sh` controls how `mkarchiso` names and packages the image. `packages.x86_64` determines what gets installed into the live root filesystem, and `pacman.conf` controls which repositories and mirrors are used during that installation.

2. **`airootfs/`** (inside `profile/`) is overlaid onto the live filesystem after packages are installed. This is where system-level configuration, default files, and MuliOS branding are placed so they appear on the resulting live system.

3. **`configs/`** contains configuration for user-facing components that are included in the live environment and the installed system:
   - `kde/` configures the KDE Plasma desktop defaults.
   - `plymouth/` configures the boot splash shown during startup.
   - `fastfetch/` configures the system information banner shown in the terminal.
   - `profile/airootfs/opt/mulios-installer/` contains the native installer.

4. **`packages/`** contains MuliOS-authored software:
   - `mulios-tools/` provides MuliOS-specific command-line utilities included in the image.
   - `mulios-installer/` provides installer packaging.

   These packages are built and included in the ISO alongside standard Arch packages listed in `packages.x86_64`.

5. **`scripts/`** ties everything together. `prepare.sh` sets up the environment, `build.sh` invokes `mkarchiso` against `profile/`, and `test.sh` supports testing and cleanup of build artifacts.

In short: **`profile/`** defines what goes into the ISO and how it is built, **`configs/`** and **`packages/`** define MuliOS-specific behavior and branding layered on top of stock Arch Linux, and **`scripts/`** automate the process of turning all of this into a bootable image.

## Development Workflow

A typical development cycle looks like this:

1. **Identify the area of change.** Determine whether your change belongs in the ArchISO profile (`profile/`), a configuration area (`configs/`), a MuliOS package (`packages/`), or the build automation (`scripts/`).

2. **Make the change locally** on a feature branch, following the structure and conventions already established in that part of the repository.

3. **Rebuild the ISO** using `scripts/build.sh` (see [`building.md`](building.md)) to confirm your change is picked up correctly and does not break the build.

4. **Test the change** by booting the resulting ISO in a virtual machine, and, if relevant, walking through the MuliOS Installer flow.

5. **Iterate** on the change locally, rebuilding and retesting as needed.

6. **Submit a pull request** once the change is working and tested, following the process described in [`contributing.md`](contributing.md).

## Moving Changes from Development to Testing

Because MuliOS-Arch produces a bootable system image, changes cannot be verified through unit tests alone. The path from a local change to a validated one generally follows:

1. **Local build** — confirm the ISO builds successfully with `scripts/build.sh` after your change.
2. **Local boot test** — boot the ISO in a virtual machine (e.g., QEMU or VirtualBox) to confirm the live environment starts and behaves as expected.
3. **Functional test** — exercise the specific area you changed (e.g., verify a KDE setting, confirm Plymouth displays correctly, run a `mulios-tools` command, or step through the MuliOS Installer if the installer was affected).
4. **Pull request review** — maintainers review the change and may request additional testing or rebuilds before merging.
5. **Integration** — once merged, the change becomes part of the next build produced from `main`, which may later be included in a tagged release (see [`release-process.md`](release-process.md)).

## Related Documentation

- [`building.md`](building.md) — how to build the ISO.
- [`architecture.md`](architecture.md) — a deeper technical look at how MuliOS-Arch is assembled.
- [`contributing.md`](contributing.md) — contribution guidelines and pull request process.
- [`troubleshooting.md`](troubleshooting.md) — common issues encountered during development.
