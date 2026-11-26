#!/bin/sh
# Install MuliOS Task Manager with a "run as root" launcher. Run from project root:
#   cargo tauri build --no-bundle && sudo sh packaging/install.sh
set -e
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo: sudo sh packaging/install.sh"; exit 1; }
BIN=target/release/mulios-taskmanager
[ -f "$BIN" ] || { echo "Missing $BIN. Build first: cargo tauri build --no-bundle"; exit 1; }
command -v pkexec >/dev/null || { echo "pkexec not found. Install polkit (Debian: sudo apt install policykit-1)"; exit 1; }

install -D -m755 -o root -g root "$BIN"                                   /usr/local/bin/mulios-taskmanager
install -D -m755 -o root -g root packaging/mulios-taskmanager-root        /usr/local/bin/mulios-taskmanager-root
install -D -m644 -o root -g root packaging/org.mulios.taskmanager.policy  /usr/share/polkit-1/actions/org.mulios.taskmanager.policy
install -D -m644 -o root -g root packaging/mulios-taskmanager.desktop     /usr/share/applications/mulios-taskmanager.desktop
install -D -m644 -o root -g root src-tauri/icons/128x128.png              /usr/share/icons/hicolor/128x128/apps/mulios-taskmanager.png
command -v update-desktop-database >/dev/null && update-desktop-database /usr/share/applications || true
echo "Done. Start from the app menu, or run: mulios-taskmanager-root"
