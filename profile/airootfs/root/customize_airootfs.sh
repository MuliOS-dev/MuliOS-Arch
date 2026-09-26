#!/usr/bin/env bash
set -e

# Pre-create the live session account while building the ISO.
# Doing this at build time avoids a boot-time useradd/passwd job
# blocking SDDM and Plasma startup.
if ! id liveuser >/dev/null 2>&1; then
    useradd -m -G wheel,audio,video,network -s /bin/bash liveuser
fi

passwd -d liveuser

install -d -m 0750 /etc/sudoers.d
cat > /etc/sudoers.d/mulios-installer <<'EOF'
liveuser ALL=(ALL:ALL) NOPASSWD: ALL
EOF
chmod 0440 /etc/sudoers.d/mulios-installer
