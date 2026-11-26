# MuliOS Task Manager (Rust + Tauri)

No Electron, no Node, no hand-written JavaScript.

- `src-tauri/` Tauri 2 backend. Metrics via `sysinfo`, per-drive I/O from `/proc/diskstats`, GPU via `radeontop`.
- `src/` Leptos frontend (Rust -> WASM). `style.css` is the only styling.
- `shared/` serde types used by both.

## One-time setup (Linux)

    # Debian / Ubuntu
    sudo apt install build-essential pkg-config libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev libssl-dev patchelf
    # Arch:  sudo pacman -S base-devel webkit2gtk-4.1 gtk3 librsvg openssl patchelf

    rustup target add wasm32-unknown-unknown
    cargo install trunk tauri-cli --locked

## Build the executable

    cargo tauri build --no-bundle

Result: `target/release/mulios-taskmanager` (single binary, frontend embedded).

    ./target/release/mulios-taskmanager
    sudo install -m755 target/release/mulios-taskmanager /usr/local/bin/

Installer packages (.deb, .rpm, .AppImage) instead: `cargo tauri build`
Dev window with reload: `cargo tauri dev`

## Run as root (kill any process, AMD GPU stats)

    cargo tauri build --no-bundle
    sudo sh packaging/install.sh
    mulios-taskmanager-root          # or use "MuliOS Task Manager" in the app menu

This installs the binary to /usr/local/bin (root:root, 755) and a polkit rule, so `pkexec`
asks for your password once. It does NOT use setuid: GTK refuses to start setuid programs.
Plain `mulios-taskmanager` still runs as your normal user.

## GPU page

Backend is picked from the card vendor (a discrete AMD/NVIDIA card wins over an Intel iGPU).

- NVIDIA: uses `nvidia-smi` (comes with the NVIDIA driver). No root needed.
  Shows load, VRAM, clocks, temperature, power, memory controller load.
- AMD: needs `radeontop`. Run the app as root, or allow `sudo -n radeontop` without password.
- Intel: no live stats yet, page shows a message.
