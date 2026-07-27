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
* Calamares installer integration
* MuliOS system tools
* Custom system configurations

## System Information

| Component | Details |
|-----------|---------|
| Base Distribution | Arch Linux |
| ISO Builder | ArchISO |
| Desktop Environment | KDE Plasma |
| Installer | Calamares |
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
sudo pacman -S archiso git
```

Clone the repository:

```bash
git clone https://github.com/MuliOS-dev/MuliOS-Arch.git
cd MuliOS-Arch
```

Build the ISO:

```bash
./build.sh
```

The generated ISO will be available in the output directory.

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


* core — Base system components
* installer — Installation tools
* update — Update management
* kernel — Kernel development
* profiles — custom linux adaptative system

You can find more projects under the "MuliOS-dev" Organisation.

## License

This project is licensed under the GNU General Public License v3.0.

See the `LICENSE` file for more information.

## Status

MuliOS Arch is currently under active development.

Features, components, and structure may change as the project evolves.
