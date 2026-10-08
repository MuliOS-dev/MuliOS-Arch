<p align="left">
  <img width="150" height="150" alt="MuliOS Arch Logo" src="https://github.com/user-attachments/assets/47400f57-be23-4a2a-be01-9e26ac0c9a1d">
</p>

# MuliOS Arch

MuliOS Arch is the **Arch Linux-based edition of MuliOS**, built with **Archiso**.

This repository contains the source files, configurations, packages, scripts, and system components used to build MuliOS Arch installation media.

MuliOS Arch is designed around **choice, performance, customization, and simplicity**.

> **People change, your OS too.**

---

## About

MuliOS Arch combines the flexibility of Arch Linux with a customized MuliOS desktop and system experience.

The project includes:

* Custom Archiso configuration
* KDE Plasma desktop environment
* Custom MuliOS branding and theming
* MuliOS Installer
* MUpdate
* MuliOS Welcome and changelog
* Built-in system tools
* Custom Fastfetch integration
* Custom SDDM login experience
* Profile infrastructure
* Custom kernel and system configuration
* Customized boot and UEFI configuration

---

## System Information

| Component           | Details            |
| ------------------- | ------------------ |
| Base Distribution   | Arch Linux         |
| ISO Builder         | Archiso            |
| Desktop Environment | KDE Plasma         |
| Installer           | MuliOS Installer   |
| Architecture        | x86_64             |
| Init System         | systemd            |
| Package Manager     | pacman             |
| Update System       | MUpdate            |
| Profiles            | MuliOS Profiles    |
| Development Status  | Active Development |
| License             | GNU GPL v3.0       |
| Repository Type     | Open Source        |

---

## Repository Structure

```text
MuliOS-Arch/
├── profile/
│   ├── airootfs/
│   ├── efiboot/
│   ├── grub/
│   ├── syslinux/
│   ├── packages.x86_64
│   ├── pacman.conf
│   ├── profiledef.sh
│   └── version
│
├── scripts/
│   ├── build.sh
│   ├── prepare.sh
│   └── test.sh
│
├── docs/
├── temp/
└── output/
```

The `profile/airootfs/` directory contains the filesystem that is installed into the live environment and provides many of the components included in the final system.

---

## Building for Developers

### Requirements

A working Arch Linux environment is required.

Install the required build tools:

```bash
sudo pacman -S --needed archiso git base-devel squashfs-tools mtools dosfstools libisoburn curl nbd
```

Clone the repository:

```bash
git clone https://github.com/MuliOS-dev/MuliOS-Arch.git
cd MuliOS-Arch
```

Build the ISO:

```bash
./scripts/build.sh
```

The generated ISO will be placed in:

```text
output/
```

For a clean rebuild:

```bash
sudo rm -rf temp output
./scripts/build.sh
```

Do not commit generated `temp/` or `output/` build data.

---

## Testing

MuliOS Arch can be tested in a virtual machine before being deployed to physical hardware.

The repository includes testing scripts and the ISO can be booted using QEMU or another compatible virtualization platform.

Always test major changes to:

* Boot configuration
* Installer functionality
* Package configuration
* Desktop configuration
* MUpdate
* Profiles
* Hardware support

before considering them ready for release.

---

## MUpdate

MuliOS Arch uses **MUpdate** to update supported files on an installed MuliOS system.

```bash
sudo mupdate update
```

MUpdate synchronizes files from:

```text
profile/airootfs/
```

with their corresponding installed locations.

The current system uses Git blob verification to identify files that have changed.

MUpdate also supports:

* `--dry-run`
* `--safe`
* `--force` / `-f`
* Automatic backups of replaced files
* Git blob verification
* Self-updating
* Resilient update handling
* MuliOS desktop/theme synchronization

Example:

```bash
sudo mupdate update --dry-run
```

MUpdate does **not** reconstruct or flash an ISO when performing a normal system update.

Machine-specific and sensitive system files are protected from synchronization.

See [`docs/mupdate.md`](docs/mupdate.md) for detailed information.

---

## MuliOS Components

MuliOS Arch contains several custom components developed specifically for the distribution.

### MuliOS Installer

A standalone graphical installer used to install and configure MuliOS Arch.

### MuliOS Welcome

A local application that introduces users to MuliOS and displays important release and changelog information.

### Task Manager

A built-in system monitoring application providing information about CPU, memory, GPU, disk, network, and running processes.

### MuliOS Credits

Displays project contributors and MuliOS project information.

### Desktop Integration

MuliOS includes customized KDE Plasma configuration, themes, wallpapers, Fastfetch integration, SDDM configuration, and other desktop components.

---

## Profiles

MuliOS Arch is designed around configurable system profiles.

Current profile concepts include:

* **Game Focused**
* **Code**
* **AI**
* **Study**
* **Privacy**
* **Casual**

Profiles can influence installed software, system configuration, and performance-related settings.

The profile system is actively evolving.

---

## Development

MuliOS Arch follows a build-and-test development workflow:

1. Changes are made in the repository.
2. The ISO is built with Archiso.
3. The resulting system is tested.
4. Problems are identified and corrected.
5. Changes are reviewed before release.

Development is primarily focused on improving reliability, usability, customization, and hardware compatibility.

---

## Contributing

Contributions are welcome.

Before contributing:

* Read the documentation in `docs/`.
* Test your changes.
* Keep commits clear and descriptive.
* Avoid unnecessary changes.
* Do not commit generated build files.
* Test changes to the installer, boot system, and desktop environment carefully.

For major architectural changes, discuss the change with the development team before implementation.

---

## Related Projects

MuliOS Arch is part of the wider MuliOS ecosystem.

* **MuliOS** — Main project and organization
* **MuliOS Installer** — Graphical installation system
* **MUpdate** — MuliOS update system
* **MuliOS-Ubuntu** — Ubuntu-based MuliOS edition
* **MuliOS Profiles** — Profile and configuration infrastructure

Additional projects are available under the [MuliOS-dev organization](https://github.com/MuliOS-dev).

---

## License

MuliOS Arch is licensed under the **GNU General Public License v3.0**.

See the `LICENSE` file for the full license text.

---

## Status

**MuliOS Arch is under active development.**

The project is continuously evolving. Features, system components, profiles, installer behavior, and internal structure may change between releases.

The Arch edition is currently the primary actively developed MuliOS distribution.

---

<div align="center">

## MuliOS Arch

**People change, your OS too.**

`Build • Customize • Experiment • Use`

</div>
