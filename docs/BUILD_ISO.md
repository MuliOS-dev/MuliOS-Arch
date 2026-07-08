# MuliOS ISO Build Guide

Minimal guide to build the MuliOS ISO using `scripts/build.sh`.

The build starts from the official Xubuntu ISO, applies MuliOS changes, and generates a new bootable ISO.

Do not commit generated ISO files.

---

## 1. Supported build environments

Recommended environments:

```text
Linux host: supported directly
macOS host: use Docker Desktop
Windows host: use Docker Desktop with WSL2 backend
```

The build script uses Linux-specific tools such as:

```text
mount
chroot
unsquashfs
mksquashfs
xorriso
apt-get
```

For this reason, the build must run in a Linux environment.

---

## 2. Clone the repository

```bash
git clone https://github.com/AxonShell/MuliOS.git
cd MuliOS
```

If the repository is already cloned:

```bash
cd MuliOS
git pull
```

---

## 3. Build on Linux

On a native Linux machine, install the required tools:

```bash
sudo apt-get update
sudo apt-get install -y \
  bash curl xorriso squashfs-tools rsync util-linux coreutils \
  grep sed gawk findutils file ca-certificates gnupg
```

Then run the build:

```bash
sudo env \
BASE_ISO_URL="https://cdimage.ubuntu.com/xubuntu/releases/resolute/release/xubuntu-26.04-desktop-amd64.iso" \
BASE_ISO_SHA256="ae030dbd99426a4c7b2d1c96731e0f435ec9d18f6a28c9e76f077dd5f46364bc" \
MULIOS_BUILD_TYPE="dev" \
./scripts/build.sh
```

Expected final message:

```text
==> MuliOS Build Completed Successfully
```

---

## 4. Build with Docker

Use this method on macOS, Windows, or any system where you do not want to install build tools directly.

Start the Docker build environment from the repository root:

```bash
docker run --rm -it --platform linux/amd64 --privileged \
  -v "$PWD:/work" \
  -v mulios-build-cache:/build_workspace \
  -w /work \
  ubuntu:24.04 \
  bash
```

On Windows PowerShell, use:

```powershell
docker run --rm -it --platform linux/amd64 --privileged `
  -v "${PWD}:/work" `
  -v mulios-build-cache:/build_workspace `
  -w /work `
  ubuntu:24.04 `
  bash
```

Inside Docker, install the required tools:

```bash
apt-get update
apt-get install -y \
  bash curl xorriso squashfs-tools rsync util-linux coreutils \
  grep sed gawk findutils file ca-certificates gnupg
```

Then run the build:

```bash
BASE_ISO_URL="https://cdimage.ubuntu.com/xubuntu/releases/resolute/release/xubuntu-26.04-desktop-amd64.iso" \
BASE_ISO_SHA256="ae030dbd99426a4c7b2d1c96731e0f435ec9d18f6a28c9e76f077dd5f46364bc" \
MULIOS_BUILD_TYPE="dev" \
MULIOS_BUILD_DIR="/build_workspace" \
./scripts/build.sh
```

Expected final message:

```text
==> MuliOS Build Completed Successfully
```

Important Docker notes:

```text
/work is the Git repository.
/build_workspace is a Linux-native Docker volume.
Always use MULIOS_BUILD_DIR="/build_workspace" when building with Docker.
Do not use /work/build_workspace on macOS or Windows.
```

---

## 5. Build type

For local testing:

```bash
MULIOS_BUILD_TYPE="dev"
```

For release builds:

```bash
MULIOS_BUILD_TYPE="release"
```

Development builds are faster. Release builds are slower but should produce smaller ISO files.

---

## 6. Output files

Generated files are written to:

```text
dist/
```

Expected output:

```text
dist/MuliOS-26.04-desktop-amd64.iso
dist/MuliOS-26.04-desktop-amd64.iso.sha256
dist/MuliOS-26.04-desktop-amd64.iso.eltorito.txt
dist/MuliOS-26.04-desktop-amd64.iso.file.txt
dist/MuliOS-26.04-desktop-amd64.iso.system-area.txt
```

Verify checksum:

```bash
cd dist
sha256sum -c MuliOS-26.04-desktop-amd64.iso.sha256
cd ..
```

Expected result:

```text
MuliOS-26.04-desktop-amd64.iso: OK
```

---

## 7. Git safety

Do not commit generated ISO files.

Before committing, always run:

```bash
git status --short
```

Build artifacts should not appear in Git status.

The repository should ignore:

```gitignore
*.iso
*.iso.sha256
build_workspace/
dist/
```

---

## 8. Test the ISO

Test the generated ISO in a VM.

Recommended VM settings:

```text
Architecture: x86_64
RAM: 4096 MiB minimum, 8192 MiB recommended
CPU: 2 minimum, 4 recommended
Disk: 30 GB
Boot ISO: dist/MuliOS-26.04-desktop-amd64.iso
Network: NAT / Shared Network
```

Expected GRUB entries:

```text
Try or Install MuliOS
MuliOS (safe graphics)
Boot from next volume
UEFI Firmware Settings
```

If normal boot gives a black screen, retry with:

```text
MuliOS (safe graphics)
```

---

## 9. Runtime checks

Inside the live desktop, open a terminal and run:

```bash
cat /etc/os-release
hostname
```

Expected `/etc/os-release`:

```text
NAME="MuliOS"
PRETTY_NAME="MuliOS 26.04.01E"
ID=mulios
```

Current known issue:

```text
hostname may still return xubuntu
```

This is expected for now.

---

## 10. Current validation status

The generated ISO has been tested in a VM and reaches the KDE Plasma live desktop.

Validated:

```text
UEFI boot: passed
GRUB boot menu: passed
MuliOS GRUB branding: passed
Kernel/initrd boot: passed
Casper live boot: passed
KDE Plasma desktop startup: passed
/etc/os-release MuliOS branding: passed
```

Known remaining issues:

```text
Live username still xubuntu
Live hostname still xubuntu
Installer desktop shortcut still says Install Xubuntu 26.04
Xubuntu splash/wallpaper branding remains
```

These are branding cleanup issues, not build failures.

---

## 11. Common problems

### Download fails

Resume manually:

```bash
curl -L -C - \
  -o /build_workspace/base.iso \
  "https://cdimage.ubuntu.com/xubuntu/releases/resolute/release/xubuntu-26.04-desktop-amd64.iso"
```

Then verify:

```bash
echo "ae030dbd99426a4c7b2d1c96731e0f435ec9d18f6a28c9e76f077dd5f46364bc  /build_workspace/base.iso" | sha256sum -c -
```

Expected:

```text
/build_workspace/base.iso: OK
```

### Docker build has filesystem errors

Make sure Docker was started with:

```bash
-v mulios-build-cache:/build_workspace
```

and the build command includes:

```bash
MULIOS_BUILD_DIR="/build_workspace"
```

### VM boots to black screen

Use:

```text
MuliOS (safe graphics)
```

or edit the GRUB entry, remove:

```text
quiet splash
```

and add:

```text
nomodeset
```

---
