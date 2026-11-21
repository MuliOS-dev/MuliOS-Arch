# MuliOS Task Manager (Rust + Tauri)

Rewrite of the Electron/Node/PySide task manager. No JavaScript, no Node.

- `src-tauri/` – Tauri 2 backend (Rust). Metrics via `sysinfo`, per-drive I/O from `/proc/diskstats`, GPU via `radeontop`.
- `src/` – Leptos 0.7 frontend (Rust → WASM), charts drawn as SVG.
- `shared/` – serde types shared by both sides.

## Prerequisites

- Rust + `rustup target add wasm32-unknown-unknown`
- `cargo install trunk tauri-cli --locked`
- Tauri Linux deps (Debian/Ubuntu): `libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev build-essential`
- Optional, AMD GPU page: `radeontop` (run as root or allow `sudo -n radeontop`)

## Run / build

    cargo tauri dev        # hot-reload dev window
    cargo tauri build      # release bundle in target/release/bundle

Replace the placeholder icon with `cargo tauri icon path/to/logo.png`.

## Notes vs. the old version

- Disk activity is now real (`/proc/diskstats`, per drive); the random fake I/O fallback was removed.
- The old "Memory Modules" card needed `dmidecode` (root) and was replaced by a swap card.
- Killing a process uses `sysinfo`'s kill (SIGKILL) with an in-app confirm dialog.
