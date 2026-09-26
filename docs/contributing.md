# Contributing to MuliOS-Arch

Thank you for your interest in contributing to MuliOS-Arch. This document explains how to contribute effectively, what is expected of contributors, and how changes are reviewed and merged.

MuliOS-Arch is maintained by a small team, and consistent, well-tested contributions help keep the ISO reliable for everyone who builds and uses it.

## Ways to Contribute

You can contribute to MuliOS-Arch in several ways:

- Fixing bugs in build scripts, packaging, or configuration.
- Improving or updating the ArchISO profile (`profile/`).
- Improving KDE, Plymouth, or Fastfetch configuration (`configs/`).
- Developing or improving MuliOS tools (`packages/mulios-tools/`) or the installer package (`packages/mulios-installer/`).
- Improving documentation.
- Reporting issues with clear reproduction steps.

## Before You Start

1. Check open issues and pull requests to avoid duplicating work.
2. For significant changes (new tools, structural changes to the profile, or changes affecting the installer), open an issue first to discuss the approach with maintainers before writing code.
3. Make sure you can successfully build the ISO locally by following [`building.md`](building.md). Being able to reproduce a working build is a prerequisite for testing your changes.

## Development Setup

Fork the repository, clone your fork, and create a feature branch:

```bash
git clone https://github.com/<your-username>/MuliOS-Arch.git
cd MuliOS-Arch
git checkout -b fix/plymouth-theme-path
```

Use descriptive branch names that reflect the change being made, for example:

- `fix/...` for bug fixes
- `feature/...` for new functionality
- `docs/...` for documentation-only changes

## Commit Quality

Clear commit history makes the project easier to maintain and debug over time. When committing changes:

- Write commit messages in the imperative mood (e.g., "Fix Plymouth theme path" rather than "Fixed" or "Fixes").
- Keep the first line under 72 characters, with additional detail in the body if needed.
- Make focused commits. Avoid bundling unrelated changes (e.g., a packaging fix and a documentation update) into a single commit.
- Reference related issues where applicable, e.g., `Fixes #42`.

Example of a good commit message:

```
Fix incorrect Calamares branding path

The branding configuration referenced a logo path that did not
match the file shipped in configs/calamares/branding. Updated
the path so the installer displays the correct MuliOS logo.

Fixes #58
```

## Testing Before Submitting Changes

All changes must be tested locally before submitting a pull request. At minimum:

1. Build the ISO using `scripts/build.sh` to confirm the profile still builds successfully.
2. Boot the resulting ISO in a virtual machine to confirm the live environment starts correctly.
3. If your change affects the installer, run through the Calamares installation flow in a virtual machine.
4. If your change affects packages, tools, or scripts, run `scripts/test.sh` if applicable, and manually verify the affected functionality.

Include a summary of how you tested your change in the pull request description. Changes that cannot be reasonably tested (e.g., environment-specific issues) should clearly state that limitation.

## Pull Requests

When you are ready to submit your change:

1. Push your branch to your fork.
2. Open a pull request against the `main` branch of MuliOS-Arch.
3. Fill out the pull request description with:
   - A summary of the change and why it is needed.
   - Any related issue numbers.
   - Steps you took to test the change.
   - Any known limitations or follow-up work.

### Review Process

- Maintainers will review pull requests for correctness, build reliability, and consistency with the rest of the project.
- You may be asked to make changes before a pull request is merged. This is a normal part of collaborative development.
- Keep pull requests reasonably small and focused. Large, sweeping changes are harder to review and more likely to introduce regressions.
- Pull requests that break the build, fail to boot, or lack any testing information may be sent back for revision before review continues.

## Code and Configuration Style

- Follow the existing structure and conventions used in `profile/` and `configs/` rather than introducing new patterns unnecessarily.
- Shell scripts should be POSIX-compatible where practical and should fail loudly (non-zero exit codes) on errors rather than failing silently.
- Keep configuration changes minimal and well-commented, especially in `airootfs/`, `calamares/`, and bootloader configuration, since these areas are easy to break in ways that only appear at boot or install time.

## Getting Help

If you are unsure how something works, open a discussion or issue rather than guessing, especially around ArchISO internals, Calamares configuration, or bootloader behavior. See [`development.md`](development.md) for an overview of how the pieces of the repository fit together.
