# Troubleshooting

This guide covers common issues developers encounter while building, testing, or modifying MuliOS-Arch, along with steps to diagnose and resolve them. If you run into an issue not covered here, please open an issue on GitHub with as much detail as possible, including your build environment and the full error output.

## General Debugging Approach

When something goes wrong, follow this general process before diving into specific fixes:

1. **Reproduce with a clean environment.** Run `sudo rm -rf work/ out/` (or `scripts/test.sh --clean` if available) and rebuild from scratch. Many issues stem from stale work directories left over from a previous build.
2. **Read the full build output.** `mkarchiso` and pacman output can be verbose, but the actual error is usually near the point where the build stopped, not necessarily at the very end.
3. **Isolate the change.** If a build worked before your changes and fails now, check whether reverting your most recent edit resolves the issue. This quickly narrows down whether the problem is in `profile/`, `configs/`, `packages/`, or `scripts/`.
4. **Check upstream Arch Linux status.** Since MuliOS-Arch depends on official Arch repositories, temporary mirror issues or upstream package changes can occasionally cause failures unrelated to your changes.

## ISO Build Failures

**Symptom:** `scripts/build.sh` exits with an error, or `mkarchiso` fails partway through.

Steps to diagnose:

- Confirm you are running the build on an up-to-date Arch Linux system with `archiso` installed, as described in [`building.md`](building.md).
- Re-run `scripts/prepare.sh` to ensure the build environment is correctly set up before running `scripts/build.sh` again.
- Check that you have sufficient disk space. ArchISO builds can fail silently or with unclear errors when the work directory runs out of space.
- Ensure the build is run with `sudo`. Many `mkarchiso` operations (like mounting filesystems) require root privileges and fail with permission errors otherwise.
- If the build fails at a specific stage (e.g., package installation vs. ISO packaging), narrow down whether the issue lies in `profile/packages.x86_64`, `profile/pacman.conf`, or the `airootfs/` overlay.

## Missing Packages

**Symptom:** The build fails with an error that a package cannot be found, or a package is missing from the resulting live environment.

Steps to diagnose:

- Confirm the package name is spelled correctly in `profile/packages.x86_64` and matches the exact name used in the Arch repositories (or a MuliOS package name from `packages/`, if applicable).
- Run `sudo pacman -Sy` to refresh your local package database before building, in case your mirror list is out of date.
- If the missing package is a MuliOS package (`mulios-tools` or `mulios-installer`), confirm it has been built and is available to the build process, since these are not part of the official Arch repositories.
- Check `profile/pacman.conf` to confirm the required repository is enabled and correctly configured, especially if the package comes from a non-default repository.

## ArchISO Errors

**Symptom:** `mkarchiso` reports errors related to the profile itself (e.g., invalid `profiledef.sh` syntax, missing required files).

Steps to diagnose:

- Verify `profile/profiledef.sh` has not been edited in a way that breaks its shell syntax. Even small typos here can cause `mkarchiso` to fail before it starts building anything.
- Confirm all directories referenced by the profile (`airootfs/`, `efiboot/`, `grub/`, `syslinux/`) exist and have not been accidentally renamed or removed.
- Check file permissions inside `airootfs/`. ArchISO is sensitive to permissions on certain files (for example, scripts that must be executable), and `profiledef.sh` may define permission rules that need to match the actual files present.
- Consult the [ArchISO documentation and Arch Wiki](https://wiki.archlinux.org/title/Archiso) for details on profile requirements if the error message references ArchISO internals rather than MuliOS-specific files.

## Boot Problems

**Symptom:** The ISO builds successfully, but fails to boot, hangs, or boots into an unexpected state in a virtual machine or on real hardware.

Steps to diagnose:

- Test the ISO in a virtual machine first (e.g., QEMU or VirtualBox) before testing on physical hardware, to rule out hardware-specific issues.
- If the ISO fails to boot under UEFI but works under BIOS (or vice versa), check the relevant bootloader configuration: `efiboot/` and `grub/` for UEFI, `syslinux/` for BIOS.
- If the system boots but Plymouth or the graphical session fails to start, check `configs/plymouth/` and `configs/kde/` for recent changes, and review any relevant logs from the live session (e.g., via a virtual console) to identify where startup is failing.
- If the failure only appeared after a change to `airootfs/`, check whether a required system file or service configuration was overwritten or removed by the overlay.

## Configuration Mistakes

**Symptom:** The system boots, but MuliOS-specific configuration does not behave as expected (incorrect branding, KDE defaults not applied, Calamares showing incorrect steps or branding, Fastfetch showing wrong output).

Steps to diagnose:

- Confirm the relevant configuration files under `configs/` are being copied into the correct location, either directly or via `airootfs/`, since misplaced files are a common cause of "my change didn't take effect" issues.
- For Calamares issues, check `configs/calamares/` for module configuration errors, such as incorrect branding paths or module ordering, which can prevent the installer from displaying correctly or completing installation.
- For KDE configuration issues, confirm default configuration files are placed in the correct user/system configuration paths expected by Plasma.
- When in doubt, compare your change against a clean checkout of `main` to identify exactly what was modified.

## Still Stuck?

If you have worked through the steps above and the issue persists:

1. Reproduce the issue with a clean build (see [`building.md`](building.md)).
2. Collect the full error output, your Arch Linux version, and the exact steps you took.
3. Open an issue on GitHub with this information so maintainers and other contributors can help investigate.
