<p align="left">
  <img width="150" height="150" alt="MuliOS Arch Logo" src="https://github.com/user-attachments/assets/47400f57-be23-4a2a-be01-9e26ac0c9a1d">
</p>

# MuliOS Arch
MuliOS Arch is the Arch Linux-based edition of **MuliOS**, built using **ArchISO**.

This repository contains the source files, configurations, and tools required to build the MuliOS Arch ISO.

## About

MuliOS Arch aims to provide a modern, customizable, and reliable Linux experience while keeping the flexibility and performance of Arch Linux.

The project includes:

* Custom ArchISO configuration
* KDE Plasma desktop environment
* MuliOS branding and customization
* MuliOS system tools
* Custom system configurations

## System Information

| Component | Details |
|-----------|---------|
| Base Distribution | Arch Linux |
| ISO Builder | ArchISO |
| Desktop Environment | KDE Plasma |
| Installer | MuliOS Installer |
| Architecture | x86_64 |
| Init System | systemd |
| Package Manager | pacman |
| Development Status | In Development |
| License | GNU GPL v3.0 |
| Repository Type | Open Source |

## Building for Developers

### Requirements

A working Arch Linux environment is required.

Install dependencies:

```bash
sudo pacman -S --needed archiso git base-devel squashfs-tools mtools dosfstools libisoburn curl
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

The generated ISO will be available in the `output/` directory.

## Updating an installed MuliOS system

MUpdate updates an installed system directly from this repository. It does not download or reconstruct an ISO and does not use a recovery environment.

```bash
sudo mupdate update
```

MUpdate compares Git blob hashes for files under `profile/airootfs/` against the corresponding installed paths. It downloads and merges only new or changed files. It does not delete files.

Live-ISO-only configuration is excluded, including live-user autologin, live installer shortcuts, ArchISO initramfs settings, and live systemd unit links. Machine-specific account, host, storage, SSH, user-data, and boot files are protected.

Preview changes before applying them:

```bash
sudo mupdate update --dry-run
```

See [`docs/mupdate.md`](docs/mupdate.md) for details and limitations.

## Development

MuliOS Arch is developed using a structured workflow:

1. Changes are made in the repository.
2. The ISO is built and tested.
3. Issues are identified and fixed.
4. Changes are reviewed before integration.

Please read the documentation in the `docs/` folder before contributing.

## Contributing

Contributions are welcome.

Before contributing:

* Read the development guidelines.
* Test your changes.
* Keep commits clear and descriptive.
* Avoid breaking existing functionality.

For major changes, discuss them with the development team before implementation.

## Related Projects to MuliOS Arch


* core-arch — Base system components
* installer-arch — Installation tools
* update — Update management
* kernel-arch — Kernel development
* profiles — custom linux adaptative system

You can find more projects under the "MuliOS-dev" Organisation.

## License

This project is licensed under the GNU General Public License v3.0.

See the `LICENSE` file for more information.

## Status

MuliOS Arch is currently under active development.

Features, components, and structure may change as the project evolves.
