#!/usr/bin/env bash
set -e

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

install -d -m 0750 /etc/sudoers.d
cat > /etc/sudoers.d/mulios-installer <<'EOF'
liveuser ALL=(ALL:ALL) NOPASSWD: ALL
EOF
chmod 0440 /etc/sudoers.d/mulios-installer
