# Building MuliOS-Arch

This guide explains how to build a MuliOS-Arch ISO image from source. It is intended for developers and contributors who need to produce a bootable image for testing or development purposes.

## Requirements

To build MuliOS-Arch, you need a machine (or virtual machine) running **Arch Linux** or an Arch-based distribution with access to the official Arch repositories. Building on non-Arch systems is not supported, since the build process depends on `archiso` and Arch-specific tooling.

Install the following packages before starting:

```bash
sudo pacman -S --needed archiso git base-devel
```

| Requirement | Purpose |
|---|---|
| `archiso` | Provides the tooling (`mkarchiso`) used to build the ISO from the profile |
| `git` | Used to clone the repository and manage contributions |
| `base-devel` | Provides build tools required by some packaging and profile scripts |

You will also need:

- A reasonably fast internet connection, since the build process downloads packages for the live environment.
- At least 10 GB of free disk space for package caches, work directories, and the final ISO.
- Root privileges (via `sudo`), since `mkarchiso` requires elevated permissions to build filesystem images.

## Cloning the Repository

Clone the repository from GitHub:

```bash
git clone https://github.com/MuliOS/MuliOS-Arch.git
cd MuliOS-Arch
```

If you are contributing changes, fork the repository first and clone your fork instead, then add the upstream repository as a remote:

```bash
git remote add upstream https://github.com/MuliOS/MuliOS-Arch.git
```

## Building the ISO

MuliOS-Arch provides helper scripts under `scripts/` so contributors do not need to memorize `mkarchiso` flags or profile paths.

### 1. Prepare the build environment

```bash
sudo ./scripts/prepare.sh
```

This script performs any setup required before a build, such as verifying dependencies are installed, syncing the package database, and preparing working directories used by the build process.

### 2. Run the build

```bash
sudo ./scripts/build.sh
```

This script wraps `mkarchiso`, pointing it at the `profile/` directory, and produces a bootable ISO image using the MuliOS-Arch ArchISO profile.

A typical build performs the following steps internally:

1. Reads configuration from `profile/profiledef.sh`.
2. Installs packages listed in `profile/packages.x86_64` into the live root filesystem.
3. Applies `airootfs/` overlay files (configuration, branding, MuliOS tools, etc.).
4. Configures bootloaders using `efiboot/`, `grub/`, and `syslinux/`.
5. Packages the result into an ISO image.

Depending on your hardware and internet speed, a full build can take anywhere from several minutes to over an hour.

## Build Output

Once the build completes, the ISO image and related artifacts are placed in the working/output directory used by `mkarchiso` (typically `work/` and `out/` inside the repository root, unless configured otherwise in `scripts/build.sh`).

Expected output includes:

- A bootable `.iso` file, named according to the profile defined in `profiledef.sh`.
- A checksum file (e.g., `.sha256`) if checksum generation is enabled.

You can test the resulting ISO using a virtual machine (such as QEMU or VirtualBox) before testing on real hardware:

```bash
qemu-system-x86_64 -m 2048 -cdrom out/mulios-arch-<version>-x86_64.iso
```

## Cleaning Build Files

ArchISO builds generate large temporary work directories that should not be committed to the repository. To remove them:

```bash
sudo ./scripts/test.sh --clean
```

If a dedicated clean option is not available in your version of the scripts, you can manually remove the generated directories:

```bash
sudo rm -rf work/ out/
```

Always clean your build environment before switching branches or pulling upstream changes, since stale work directories can cause inconsistent or failed builds.

## Next Steps

- See [`development.md`](development.md) to understand how the repository is organized and how to develop new features.
- See [`troubleshooting.md`](troubleshooting.md) if your build fails or produces unexpected results.
