# MuliOS Rust Migration

## Objective

Move MuliOS-maintained application and system-tool code toward native Rust while
keeping Arch Linux, systemd, the standard Linux kernel, Archiso, and required
upstream desktop components. This work is isolated to the `rust` branch.

The migration is incremental. Existing Python, JavaScript, and shell
implementations remain in place until Rust replacements reach feature parity
and have been validated in a booted QEMU image.

## Workspace layout

- `rust/crates/mulios-core`: shared, dependency-free system interfaces.
- `rust/apps/muliosctl`: first native MuliOS command-line utility.

The workspace root is the repository-level `Cargo.toml`.

## Initial utility

Build and run on Linux:

```sh
cargo test --workspace
cargo run -p muliosctl -- info
cargo run -p muliosctl -- version
```

The first utility reads standard, read-only Linux interfaces:

- `/etc/os-release`
- `/proc/meminfo`
- `/proc/uptime`

It does not require root and does not change system state.

## Migration order

1. Establish the Rust workspace, shared interfaces, CI, and packaging conventions.
2. Port MUpdate while preserving dry-run, safe mode, backup, integrity checking,
   protected paths, and recovery behavior.
3. Replace MuliOS-owned shell utilities with small Rust binaries where Rust
   materially improves safety or maintainability.
4. Replace the Node-based Task Manager with a native Rust application after
   mapping every API field and UI behavior.
5. Port Credits and Changelog applications.
6. Port the installer only after documenting every page, validation rule,
   partitioning action, bootloader operation, install step, and recovery path.
7. Integrate Rust binaries into Archiso and remove old runtimes only after
   dependency and boot testing proves they are no longer needed.

## Compatibility boundaries

Rust is the implementation language for MuliOS-owned code, not a requirement
to rewrite upstream software. Keep the Arch kernel, systemd, Archiso, KDE
Plasma/KWin, Qt libraries, firmware, and other upstream components intact
unless a separate, justified project decision changes that boundary.

Build orchestration may continue to call Archiso and established system tools.
A Rust wrapper does not make an external tool unnecessary.

## Release gate

A migration step is not complete merely because it compiles. It must have
unit tests, integration tests where applicable, documented runtime
dependencies, and a successful QEMU boot/install test before its predecessor
is removed.

The first milestone is a bootable MuliOS ISO using the standard Linux kernel
and systemd, with at least one Rust-native MuliOS utility available in the
live environment.
