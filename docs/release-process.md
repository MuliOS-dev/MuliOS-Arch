# Release Process

This document describes how MuliOS-Arch releases are prepared, tested, and published. It is intended for maintainers and contributors involved in cutting a new release.

A release of MuliOS-Arch consists of a built and verified ISO image, along with accompanying release notes and documentation updates, made available to the community.

## Overview of the Release Cycle

```
main branch
   │
   ▼
Testing Phase ──► ISO Verification ──► Documentation Updates
   │                                           │
   └───────────────► Release Notes ◄───────────┘
                          │
                          ▼
                  Publishing Process
```

## 1. Testing Phase

Before a release is prepared, the current state of the `main` branch should be considered feature-complete and stable for the intended release.

During this phase:

- Build the ISO from a clean environment using `scripts/build.sh`, following [`building.md`](building.md).
- Boot the resulting ISO in a virtual machine to confirm the live environment starts correctly, KDE Plasma loads as expected, and Plymouth displays correctly during boot.
- Walk through the full MuliOS Installer flow to confirm the installer completes successfully and produces a bootable installed system.
- Verify that MuliOS tools (`mulios-tools`) function correctly in the live environment and, where applicable, after installation.
- Test on both UEFI and legacy BIOS boot modes if possible, since bootloader configuration (`efiboot/`, `grub/`, `syslinux/`) differs between them.
- Where feasible, test on real hardware in addition to virtual machines, since some issues (particularly around boot and firmware) do not always surface in virtualized environments.

Any issues found during this phase should be fixed and re-tested before moving forward. Testing should be repeated after any fix to confirm the fix did not introduce a new regression.

## 2. ISO Verification

Once testing is complete and the build is considered stable:

- Perform a final clean build of the ISO intended for release, ensuring no leftover work directories or uncommitted local changes are included (see [`building.md`](building.md) for cleaning build files).
- Generate checksums (e.g., SHA-256) for the final ISO so downstream users can verify the integrity of downloaded images.
- Confirm the ISO filename and internal versioning (as defined in `profile/profiledef.sh`) matches the intended release version.
- Boot the final release candidate ISO one more time as a sanity check before publishing, since this should be the exact artifact that gets released.

## 3. Documentation Updates

Before publishing, review and update documentation as needed:

- Confirm `docs/building.md`, `docs/development.md`, and `docs/architecture.md` still accurately reflect the current state of the repository, especially if the release includes structural changes.
- Update `docs/troubleshooting.md` with any new known issues or workarounds discovered during the testing phase.
- Ensure any newly added tools, configuration options, or workflow changes introduced in this release are documented.

## 4. Release Notes

Prepare release notes summarizing the release. Release notes should typically include:

- **Summary** — a short overview of what this release represents (e.g., a stable point release, or a release focused on a specific set of fixes/improvements).
- **Changes** — a list of notable changes since the previous release, grouped where helpful (e.g., ISO/build changes, desktop/KDE changes, installer changes, MuliOS tools changes).
- **Known issues** — any known limitations or issues that were not resolved before release, so users are aware of them in advance.
- **Upgrade/installation notes** — anything users should be aware of when installing this release, particularly if the installation flow or partitioning behavior has changed.

Release notes should be written clearly enough that someone who has not been following development closely can understand what changed and why it matters.

## 5. Publishing Process

Once the ISO is verified and documentation and release notes are ready:

1. Tag the release in Git using a version number consistent with the project's versioning scheme, and push the tag to the repository.
2. Attach the final ISO image and its checksum file to the corresponding GitHub release.
3. Publish the release notes alongside the release on GitHub.
4. Announce the release through the project's usual communication channels, if applicable.

After publishing, monitor incoming issue reports closely for the first period following release, since real-world usage across a wider range of hardware often surfaces issues that were not caught during testing.

## Related Documentation

- [`building.md`](building.md) — building the ISO that will become the release candidate.
- [`contributing.md`](contributing.md) — how contributions leading up to a release are submitted and reviewed.
- [`troubleshooting.md`](troubleshooting.md) — resolving issues found during the testing phase.
