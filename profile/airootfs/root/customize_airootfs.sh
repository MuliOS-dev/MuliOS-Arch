#!/usr/bin/env bash
set -e

# Pre-create the live session account while building the ISO.
if ! id liveuser >/dev/null 2>&1; then
    useradd -m -G wheel,audio,video,network -s /bin/bash liveuser
fi

passwd -d liveuser

install -d -m 0750 /etc/sudoers.d
cat > /etc/sudoers.d/mulios-installer <<'EOF'
liveuser ALL=(ALL:ALL) NOPASSWD: ALL
EOF
chmod 0440 /etc/sudoers.d/mulios-installer

# Build the Task Manager's native C backend inside the target rootfs.
TASKMANAGER_SRC=/opt/taskmanager/backend/taskmanager.c
TASKMANAGER_BIN=/opt/taskmanager/backend/taskmanager

if [ -f "$TASKMANAGER_SRC" ]; then
    gcc -O2 -pipe -Wall -Wextra -o "$TASKMANAGER_BIN" "$TASKMANAGER_SRC"
    chmod 0755 "$TASKMANAGER_BIN"
fi
