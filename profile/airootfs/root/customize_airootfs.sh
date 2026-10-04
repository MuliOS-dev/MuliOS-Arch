#!/usr/bin/env bash
set -e

# KDE Plasma 6 application menu compatibility
# Plasma 6 ships its canonical menu as plasma-applications.menu.
# KService may still resolve applications.menu depending on the session
# environment. Keep both paths valid so Kickoff never starts with an empty
# application database in the live ISO.
install -d -m 0755 /etc/xdg/menus
if [ -f /etc/xdg/menus/plasma-applications.menu ]; then
    ln -sfn plasma-applications.menu /etc/xdg/menus/applications.menu
fi

install -d -m 0755 /etc/profile.d
cat > /etc/profile.d/mulios-kde-menu.sh <<'EOF'
# KDE Plasma 6 uses the plasma- XDG menu prefix.
export XDG_MENU_PREFIX=plasma-
EOF
chmod 0644 /etc/profile.d/mulios-kde-menu.sh

# Pre-create the live session account while building the ISO.
if ! id liveuser >/dev/null 2>&1; then
    useradd -m -G wheel,audio,video,network -s /bin/bash liveuser
fi

passwd -d liveuser

# useradd normally copies /etc/skel, but explicitly synchronize the desktop
# defaults so rebuilds remain deterministic if the account already exists.
if [ -d /etc/skel/.config ]; then
    install -d -o liveuser -g liveuser /home/liveuser/.config
    cp -a /etc/skel/.config/. /home/liveuser/.config/
fi

if [ -d /etc/skel/Desktop ]; then
    install -d -o liveuser -g liveuser /home/liveuser/Desktop
    cp -a /etc/skel/Desktop/. /home/liveuser/Desktop/
fi

chown -R liveuser:liveuser /home/liveuser/.config /home/liveuser/Desktop 2>/dev/null || true

# Build the live user's KService database after /etc/skel and the live
# account exist. Plasma 6 expects the plasma- menu prefix.
if id liveuser >/dev/null 2>&1 && command -v kbuildsycoca6 >/dev/null 2>&1; then
    install -d -o liveuser -g liveuser /home/liveuser/.cache
    rm -f /home/liveuser/.cache/ksycoca6_* 2>/dev/null || true
    runuser -u liveuser -- env         XDG_MENU_PREFIX=plasma-         kbuildsycoca6 --noincremental --global || true
fi

install -d -m 0750 /etc/sudoers.d
cat > /etc/sudoers.d/mulios-installer <<'EOF'
liveuser ALL=(ALL:ALL) NOPASSWD: ALL
EOF
# Guarantee the live installer launcher is executable in the final airootfs.
# mkarchiso preserves the source-tree mode, so enforce it here as well as in
# the build script.
if [ -f /usr/local/bin/mulios-installer ]; then
    chmod 0755 /usr/local/bin/mulios-installer
fi

chmod 0440 /etc/sudoers.d/mulios-installer
