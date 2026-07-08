#!/usr/bin/env bash
set -euo pipefail

# ====================================================================
# MuliOS System Customization and Tweak Script
# Target: Xubuntu base migrated to KDE Plasma / SDDM
#
# This script runs inside the build chroot.
# Keep it deterministic: no network downloads, no curl|bash, no host-specific state.
# ====================================================================

export DEBIAN_FRONTEND=noninteractive

echo "==> [1/5] Applying MuliOS identity..."

# Keep hostname simple and RFC-safe.
echo "mulios" > /etc/hostname

# Keep /etc/hosts consistent with the hostname when the file exists.
if [ -f /etc/hosts ]; then
    if grep -qE '^127\.0\.1\.1[[:space:]]+' /etc/hosts; then
        sed -i 's/^127\.0\.1\.1.*/127.0.1.1\tmulios/' /etc/hosts
    else
        printf '127.0.1.1\tmulios\n' >> /etc/hosts
    fi
fi

cat > /etc/os-release <<'EOF'
NAME="MuliOS"
VERSION="26.04.01E"
ID=mulios
ID_LIKE="ubuntu debian"
PRETTY_NAME="MuliOS 26.04.01E"
VERSION_ID="26.04"
HOME_URL="https://github.com/AxonShell/MuliOS"
SUPPORT_URL="https://github.com/AxonShell/MuliOS/issues"
BUG_REPORT_URL="https://github.com/AxonShell/MuliOS/issues"
EOF

echo "==> [2/5] Selecting SDDM as default display manager..."

# Preseed the display-manager choice when debconf is available.
if command -v debconf-set-selections >/dev/null 2>&1; then
    echo "sddm shared/default-x-display-manager select sddm" | debconf-set-selections
fi

mkdir -p /etc/X11
echo "/usr/bin/sddm" > /etc/X11/default-display-manager

# Enable SDDM without trying to start services in the chroot.
# The build system also provides policy-rc.d, but direct symlink creation is deterministic.
if [ -f /lib/systemd/system/sddm.service ]; then
    mkdir -p /etc/systemd/system
    ln -sfn /lib/systemd/system/sddm.service /etc/systemd/system/display-manager.service
fi

echo "==> [3/5] Disabling inherited Ubuntu crash reporting defaults..."

if [ -f /etc/default/apport ]; then
    sed -i 's/^enabled=1/enabled=0/' /etc/default/apport
fi

echo "==> [4/5] Keeping generated installs unique..."

# Do not ship a static machine-id in the ISO rootfs.
truncate -s 0 /etc/machine-id || true
rm -f /var/lib/dbus/machine-id || true
ln -sf /etc/machine-id /var/lib/dbus/machine-id || true

echo "==> [5/5] Final lightweight cleanup..."

# Package removal/autoremove/cache cleanup is mainly handled by build.sh.
# This remains intentionally small to avoid hiding build logic inside the tweak script.
rm -rf /tmp/* /var/tmp/*

echo "==> MuliOS setup tweaks completed."