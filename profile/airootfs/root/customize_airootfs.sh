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

# Ensure core home & XDG directories exist with liveuser ownership before
# copying skeleton files or running user-level cache builders.
install -d -o liveuser -g liveuser -m 0755 \
    /home/liveuser \
    /home/liveuser/.config \
    /home/liveuser/.local \
    /home/liveuser/.local/share \
    /home/liveuser/.cache \
    /home/liveuser/Desktop

# useradd normally copies /etc/skel, but explicitly synchronize the desktop
# defaults so rebuilds remain deterministic if the account already exists.
if [ -d /etc/skel/.config ]; then
    cp -a /etc/skel/.config/. /home/liveuser/.config/
fi

if [ -d /etc/skel/.local ]; then
    cp -a /etc/skel/.local/. /home/liveuser/.local/
fi

if [ -d /etc/skel/Desktop ]; then
    cp -a /etc/skel/Desktop/. /home/liveuser/Desktop/
fi

# Force the canonical MuliOS Fastfetch configuration for the live user.
# Remove every legacy per-user Fastfetch format before the ISO is finalized.
if [ -f /etc/fastfetch/config.jsonc ]; then
    install -d -o liveuser -g liveuser -m 0755 /home/liveuser/.config/fastfetch
    install -o liveuser -g liveuser -m 0644 /etc/fastfetch/config.jsonc /home/liveuser/.config/fastfetch/config.jsonc
fi
rm -f /home/liveuser/.config/fastfetch/config.conf /home/liveuser/.config/fastfetch/config.json

# Build the live user's KService database after /etc/skel and the live
# account exist. Plasma 6 expects the plasma- menu prefix.
if id liveuser >/dev/null 2>&1 && command -v kbuildsycoca6 >/dev/null 2>&1; then
    rm -f /home/liveuser/.cache/ksycoca6_* 2>/dev/null || true
    runuser -u liveuser -- env \
        HOME=/home/liveuser \
        XDG_CONFIG_HOME=/home/liveuser/.config \
        XDG_DATA_HOME=/home/liveuser/.local/share \
        XDG_CACHE_HOME=/home/liveuser/.cache \
        XDG_MENU_PREFIX=plasma- \
        kbuildsycoca6 --noincremental || true
fi

# Final ownership sweep so no file created during customization remains root-owned.
chown -R liveuser:liveuser /home/liveuser 2>/dev/null || true

install -d -m 0750 /etc/sudoers.d
cat > /etc/sudoers.d/mulios-installer <<'EOF'
liveuser ALL=(ALL:ALL) NOPASSWD: ALL
EOF
chmod 0440 /etc/sudoers.d/mulios-installer

# Guarantee the live installer and helper launchers are executable in the final
# airootfs. mkarchiso preserves the source-tree mode, so enforce it here as
# well as in the build script.
for launcher in \
    /usr/local/bin/mulios-installer \
    /usr/local/bin/mulios-taskmanager \
    /usr/local/bin/mulios-credits \
    /usr/local/bin/mulios-apply-wallpaper \
    /usr/local/bin/mulios-wallpaper-autostart
do
    if [ -f "$launcher" ]; then
        chmod 0755 "$launcher"
    fi
done

# The menu entry's TryExec points to the compiled application. Keep its
# executable bit explicit in the final live filesystem as well.
if [ -f /usr/bin/mulios-taskmanager ]; then
    chmod 0755 /usr/bin/mulios-taskmanager
fi