from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal


LOG_PATH = Path("/var/log/mulios/install.log")
TARGET = Path("/mnt")
SWAP_SIZE = "4G"


class InstallError(RuntimeError):
    pass


class InstallWorker(QThread):
    progress = Signal(int)
    log_line = Signal(str)
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, state: dict, parent=None):
        super().__init__(parent)

        self.state = dict(state)
        self.target = TARGET

        self.mapped_root = None
        self.mounts_active = False
        self.pacman_synced = False
        self.network_available = False
        self.selected_disk = None
        self.boot_partition = None
        self.root_partition = None
        self.root_device = None
        self.kernel_package = "linux"

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def initialize_log(self):
        try:
            LOG_PATH.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with LOG_PATH.open(
                "a",
                encoding="utf-8",
            ) as f:
                f.write("\n")
                f.write("=" * 80 + "\n")
                f.write("MuliOS Native Installer\n")
                f.write("=" * 80 + "\n")
                f.write(f"PID: {os.getpid()}\n")
                f.write(f"UID: {os.geteuid()}\n")
                f.write("=" * 80 + "\n")
                f.flush()

            return True

        except Exception as exc:
            message = (
                "CRITICAL: Could not initialize installer log: "
                f"{type(exc).__name__}: {exc}"
            )

            try:
                self.log_line.emit(message)
            except Exception:
                pass

            raise InstallError(message) from exc

    def log(self, message: str, *, visible=True):
        message = str(message)

        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

            with LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(message + "\n")
                f.flush()

        except Exception as exc:
            try:
                self.log_line.emit(
                    f"LOGGING ERROR: {exc}"
                )
            except Exception:
                pass

        try:
            if visible:
                self.log_line.emit(message)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def run_command(
        self,
        command,
        *,
        check=True,
        input_text=None,
        env=None,
        progress_range=None,
    ):
        command = [str(x) for x in command]

        display_command = " ".join(
            shlex.quote(x)
            for x in command
        )

        self.log(f"$ {display_command}", visible=False)

        try:
            process = subprocess.Popen(
                command,
                stdin=(
                    subprocess.PIPE
                    if input_text is not None
                    else None
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                bufsize=1,
            )

        except Exception as exc:
            self.log(
                f"FAILED TO START COMMAND: {display_command}"
            )
            self.log(
                f"Exception: {type(exc).__name__}: {exc}"
            )
            raise InstallError(
                f"Could not start command: {display_command}: {exc}"
            ) from exc

        if input_text is not None and process.stdin is not None:
            try:
                process.stdin.write(input_text)
                process.stdin.close()
            except Exception as exc:
                self.log(
                    f"WARNING: Could not write command input: {exc}"
                )
                try:
                    process.stdin.close()
                except Exception:
                    pass

        output = []

        try:
            if process.stdout is not None:
                for line in process.stdout:
                    line = line.rstrip("\n")
                    output.append(line)

                    # Keep command output in the full log, but never flood
                    # the active installer view with rsync/pacman byte
                    # counters, transfer rates, or per-file status.
                    self.log(line, visible=False)

                    if progress_range is not None:
                        matches = re.findall(
                            r"(?<!\d)([\d,]+)\s+(\d{1,3})%(?:\s|$)",
                            line,
                        )
                        if matches:
                            percent = min(
                                100,
                                int(matches[-1][1]),
                            )
                            start, end = progress_range
                            value = int(
                                start +
                                ((end - start) * percent / 100.0)
                            )
                            self.progress.emit(value)

        except Exception as exc:
            self.log(
                f"ERROR while reading command output: "
                f"{type(exc).__name__}: {exc}"
            )

        process.wait()

        self.log(
            f"[exit code: {process.returncode}]",
            visible=False,
        )

        result = "\n".join(output)

        if check and process.returncode != 0:
            self.log(
                f"COMMAND FAILED: {display_command}"
            )

            raise InstallError(
                "Command failed with exit code "
                f"{process.returncode}: "
                f"{display_command}"
            )

        return result

    def chroot(
        self,
        command,
        *,
        check=True,
        input_text=None,
    ):
        return self.run_command(
            [
                "arch-chroot",
                str(self.target),
                *command,
            ],
            check=check,
            input_text=input_text,
        )

    # ------------------------------------------------------------------
    # Basic validation
    # ------------------------------------------------------------------

    def require_root(self):
        if os.geteuid() != 0:
            raise InstallError(
                "The installer must run as root."
            )

    def is_uefi(self):
        return Path(
            "/sys/firmware/efi"
        ).exists()

    def disk(self) -> str:
        disk = str(
            self.state.get("disk", "")
        ).strip()

        if not disk.startswith("/dev/"):
            raise InstallError(
                f"Invalid installation disk: {disk}"
            )

        forbidden = {
            "/dev",
            "/dev/null",
            "/dev/zero",
            "/dev/random",
            "/dev/urandom",
        }

        if disk in forbidden:
            raise InstallError(
                f"Invalid installation disk: {disk}"
            )

        if not os.path.exists(disk):
            raise InstallError(
                f"Installation disk does not exist: {disk}"
            )

        result = subprocess.run(
            [
                "lsblk",
                "-dn",
                "-o",
                "TYPE",
                disk,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise InstallError(
                f"Could not inspect installation disk: {disk}"
            )

        if result.stdout.strip() != "disk":
            raise InstallError(
                f"Selected device is not a whole disk: {disk}"
            )

        self.selected_disk = disk

        self.check_live_media(disk)

        # Never allow a disk with active mountpoints to be erased.
        # This protects against accidentally selecting the live system,
        # WSL storage, or another disk currently in use.
        mounted_result = subprocess.run(
            [
                "lsblk",
                "-nrpo",
                "NAME,MOUNTPOINTS",
                disk,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if mounted_result.returncode != 0:
            raise InstallError(
                f"Could not inspect mountpoints on installation disk: {disk}"
            )

        mounted_paths = []

        for line in mounted_result.stdout.splitlines():
            parts = line.split(None, 1)

            if len(parts) != 2:
                continue

            mountpoint = parts[1].strip()

            if mountpoint and mountpoint != "-":
                mounted_paths.append(
                    mountpoint
                )

        if mounted_paths:
            raise InstallError(
                "The selected disk has mounted filesystems and "
                "cannot be erased: " +
                ", ".join(mounted_paths)
            )

        # Require enough space for the 1 GiB EFI partition,
        # the MuliOS installation, swap, and normal system data.
        size_result = subprocess.run(
            [
                "blockdev",
                "--getsize64",
                disk,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if size_result.returncode != 0:
            raise InstallError(
                f"Could not determine installation disk size: {disk}"
            )

        try:
            disk_size = int(
                size_result.stdout.strip()
            )
        except ValueError:
            raise InstallError(
                f"Could not parse installation disk size: {disk}"
            )

        minimum_size = 20 * 1024 * 1024 * 1024

        if disk_size < minimum_size:
            raise InstallError(
                "The selected disk is too small. "
                "MuliOS requires at least 20 GiB."
            )

        self.log(
            f"Installation disk size: "
            f"{disk_size / (1024 ** 3):.1f} GiB"
        )

        return disk

    def check_live_media(self, disk: str):
        disk_real = os.path.realpath(disk)

        if not disk_real.startswith("/dev/"):
            raise InstallError(
                f"Could not resolve installation disk: {disk}"
            )

        # Never allow the device containing the running live root
        # filesystem to be erased.
        live_mounts = [
            "/run/archiso/airootfs",
            "/run/live/airootfs",
        ]

        for mountpoint in live_mounts:
            try:
                result = subprocess.run(
                    [
                        "findmnt",
                        "-n",
                        "-o",
                        "SOURCE",
                        "--target",
                        mountpoint,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                continue

            source = result.stdout.strip()

            if not source:
                continue

            source_real = os.path.realpath(source)

            if source_real == disk_real:
                raise InstallError(
                    "The selected disk contains the running "
                    "MuliOS live media and cannot be erased."
                )

            parent_result = subprocess.run(
                [
                    "lsblk",
                    "-nrpo",
                    "PKNAME",
                    source_real,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            parent = parent_result.stdout.strip()

            if parent:
                parent_real = os.path.realpath(
                    "/dev/" + parent
                )

                if parent_real == disk_real:
                    raise InstallError(
                        "The selected disk contains the running "
                        "MuliOS live media and cannot be erased."
                    )

        # Also inspect every child device of the selected disk.
        result = subprocess.run(
            [
                "lsblk",
                "-nrpo",
                "NAME,MOUNTPOINT",
                disk,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise InstallError(
                f"Could not inspect selected disk: {disk}"
            )

        for line in result.stdout.splitlines():
            parts = line.split(None, 1)

            if len(parts) != 2:
                continue

            mountpoint = parts[1].strip()

            if mountpoint.startswith("/run/archiso"):
                raise InstallError(
                    "The selected disk contains the running "
                    "MuliOS live media and cannot be erased."
                )

            if mountpoint.startswith("/run/live"):
                raise InstallError(
                    "The selected disk contains the running "
                    "live media and cannot be erased."
                )

    def partition_names(self, disk: str):
        if (
            "nvme" in disk
            or "mmcblk" in disk
            or "loop" in disk
        ):
            return (
                disk + "p1",
                disk + "p2",
            )

        return (
            disk + "1",
            disk + "2",
        )

    # ------------------------------------------------------------------
    # Disk preparation
    # ------------------------------------------------------------------

    def unmount_disk_partitions(
        self,
        disk: str,
    ):
        result = subprocess.run(
            [
                "lsblk",
                "-nrpo",
                "NAME,TYPE",
                disk,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return

        devices = []

        for line in result.stdout.splitlines():
            parts = line.split()

            if len(parts) < 2:
                continue

            name, device_type = parts[0], parts[1]

            if (
                device_type == "part"
                and name != disk
            ):
                devices.append(name)

        for device in reversed(devices):
            self.run_command(
                [
                    "umount",
                    "-R",
                    device,
                ],
                check=False,
            )

    def partition_disk(self):
        disk = self.disk()

        boot, root = self.partition_names(
            disk
        )

        self.boot_partition = boot
        self.root_partition = root

        self.log(
            f"Preparing installation disk: {disk}"
        )

        self.progress.emit(4)

        self.run_command(
            ["swapoff", "-a"],
            check=False,
        )

        self.log(
            "Unmounting existing partitions..."
        )

        self.unmount_disk_partitions(
            disk
        )

        self.log(
            "Removing existing filesystem signatures..."
        )

        self.run_command(
            [
                "wipefs",
                "--all",
                "--force",
                disk,
            ]
        )

        self.log(
            "Creating GPT partition table..."
        )

        sfdisk_script = (
            "label: gpt\n"
            "size=1G, type=uefi, name=\"MuliOS EFI\"\n"
            "type=linux, name=\"MuliOS Root\"\n"
        )

        self.run_command(
            [
                "sfdisk",
                "--wipe",
                "always",
                disk,
            ],
            input_text=sfdisk_script,
        )

        self.run_command(
            [
                "partprobe",
                disk,
            ],
            check=False,
        )

        self.run_command(
            [
                "udevadm",
                "settle",
            ]
        )

        if not os.path.exists(boot):
            raise InstallError(
                f"EFI partition was not created: {boot}"
            )

        if not os.path.exists(root):
            raise InstallError(
                f"Root partition was not created: {root}"
            )

        self.log(
            f"EFI partition: {boot}"
        )

        self.log(
            f"Root partition: {root}"
        )

        self.progress.emit(8)

        return boot, root

    # ------------------------------------------------------------------
    # Encryption
    # ------------------------------------------------------------------

    def encryption_enabled(self) -> bool:
        return bool(
            self.state.get(
                "encrypt_disk",
                False,
            )
        )

    def prepare_encryption(
        self,
        root: str,
    ) -> str:
        if not self.encryption_enabled():
            self.root_device = root
            return root

        password = str(
            self.state.get(
                "encryption_password",
                "",
            )
        )

        if len(password) < 4:
            raise InstallError(
                "Disk encryption is enabled but "
                "the encryption password is invalid."
            )

        self.log(
            "Installing cryptsetup support..."
        )

        self.log(
            "Formatting root partition as LUKS2..."
        )

        self.run_command(
            [
                "cryptsetup",
                "luksFormat",
                "--type",
                "luks2",
                "--batch-mode",
                "--key-file=-",
                root,
            ],
            input_text=password + "\n",
        )

        self.log(
            "Opening encrypted root volume..."
        )

        self.run_command(
            [
                "cryptsetup",
                "open",
                "--key-file=-",
                root,
                "mulios-root",
            ],
            input_text=password + "\n",
        )

        mapped = Path(
            "/dev/mapper/mulios-root"
        )

        if not mapped.exists():
            raise InstallError(
                "Failed to open LUKS root volume."
            )

        self.mapped_root = str(mapped)
        self.root_device = str(mapped)

        self.log(
            "LUKS root volume opened."
        )

        return str(mapped)

    def close_encryption(self):
        if self.mapped_root is None:
            return

        self.run_command(
            [
                "cryptsetup",
                "close",
                "mulios-root",
            ],
            check=False,
        )

        self.mapped_root = None

    # ------------------------------------------------------------------
    # Filesystems
    # ------------------------------------------------------------------

    def format_filesystems(
        self,
        boot: str,
        root: str,
        mapped_root=None,
    ):
        filesystem = str(
            self.state.get(
                "filesystem",
                "ext4",
            )
        ).lower()

        filesystem_root = (
            mapped_root or root
        )

        if not os.path.exists(boot):
            raise InstallError(
                f"EFI partition does not exist: {boot}"
            )

        if not os.path.exists(root):
            raise InstallError(
                f"Root partition does not exist: {root}"
            )

        if filesystem_root != root and not os.path.exists(
            filesystem_root
        ):
            raise InstallError(
                "Encrypted root device does not exist: "
                f"{filesystem_root}"
            )

        if filesystem not in {
            "ext4",
            "btrfs",
            "xfs",
        }:
            raise InstallError(
                f"Unsupported filesystem: {filesystem}"
            )

        self.log(
            "Formatting EFI system partition..."
        )

        self.run_command(
            [
                "mkfs.fat",
                "-F",
                "32",
                "-n",
                "MULIOS_EFI",
                boot,
            ]
        )

        self.log(
            f"Formatting root filesystem as {filesystem}..."
        )

        if filesystem == "ext4":
            self.run_command(
                [
                    "mkfs.ext4",
                    "-F",
                    "-L",
                    "MULIOS_ROOT",
                    filesystem_root,
                ]
            )

        elif filesystem == "btrfs":
            self.run_command(
                [
                    "mkfs.btrfs",
                    "-f",
                    "-L",
                    "MULIOS_ROOT",
                    filesystem_root,
                ]
            )

        elif filesystem == "xfs":
            self.run_command(
                [
                    "mkfs.xfs",
                    "-f",
                    "-L",
                    "MULIOS_ROOT",
                    filesystem_root,
                ]
            )

        self.progress.emit(14)

    # ------------------------------------------------------------------
    # Filesystem mounting
    # ------------------------------------------------------------------

    def mount_filesystems(
        self,
        boot: str,
        root: str,
        mapped_root=None,
    ):
        filesystem_root = (
            mapped_root or root
        )

        self.target.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.log(
            "Mounting root filesystem..."
        )

        self.run_command(
            [
                "mount",
                filesystem_root,
                str(self.target),
            ]
        )

        # Root is mounted even if the EFI mount fails afterwards.
        # Mark cleanup as active immediately so failures cannot leave
        # /mnt mounted.
        self.mounts_active = True

        boot_mount = (
            self.target / "boot"
        )

        boot_mount.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.log(
            "Mounting EFI system partition..."
        )

        self.run_command(
            [
                "mount",
                boot,
                str(boot_mount),
            ]
        )

        self.progress.emit(20)

    # ------------------------------------------------------------------
    # Live system copying
    # ------------------------------------------------------------------

    def find_live_source(self) -> Path:
        candidates = [
            Path(
                "/run/archiso/airootfs"
            ),
            Path(
                "/run/live/airootfs"
            ),
        ]

        for candidate in candidates:
            if candidate.is_dir():
                return candidate

        raise InstallError(
            "Could not locate the MuliOS live filesystem. "
            "Expected /run/archiso/airootfs."
        )

    def copy_system(self):
        source = self.find_live_source()

        self.log(
            f"Copying MuliOS live system from {source}..."
        )

        excluded = [
            "--exclude=/dev/*",
            "--exclude=/proc/*",
            "--exclude=/sys/*",
            "--exclude=/run/*",
            "--exclude=/tmp/*",
            "--exclude=/mnt/*",
            "--exclude=/media/*",
            "--exclude=/lost+found",
        ]

        self.run_command(
            [
                "rsync",
                "-aHAX",
                "--numeric-ids",
                *excluded,
                "--info=progress2",
                "--human-readable",
                "--stats",
                f"{source}/",
                f"{self.target}/",
            ],
            progress_range=(20, 45),
        )

        for directory in (
            "dev",
            "proc",
            "sys",
            "run",
            "tmp",
        ):
            (
                self.target / directory
            ).mkdir(
                parents=True,
                exist_ok=True,
            )

        self.run_command(
            [
                "chmod",
                "1777",
                str(
                    self.target / "tmp"
                ),
            ]
        )

        self.remove_live_environment()

        self.progress.emit(45)

    def remove_live_environment(self):
        self.log(
            "Removing live-session configuration..."
        )

        self.chroot(
            [
                "userdel",
                "-r",
                "liveuser",
            ],
            check=False,
        )

        self.chroot(
            [
                "systemctl",
                "disable",
                "mulios-live-user.service",
            ],
            check=False,
        )

        service = (
            self.target /
            "etc/systemd/system/"
            "mulios-live-user.service"
        )

        if service.exists():
            service.unlink()

        sddm_dir = (
            self.target /
            "etc/sddm.conf.d"
        )

        if sddm_dir.exists():
            for path in sddm_dir.glob(
                "*autologin*"
            ):
                try:
                    path.unlink()
                except OSError:
                    pass

        for path in (
            self.target /
            "etc/sddm.conf",
            self.target /
            "etc/sddm.conf.d/autologin.conf",
        ):
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------

    def write_file(
        self,
        path: Path,
        content: str,
        mode=0o644,
    ):
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            content,
            encoding="utf-8",
        )

        os.chmod(
            path,
            mode,
        )

    # ------------------------------------------------------------------
    # Fstab / crypttab
    # ------------------------------------------------------------------

    def block_uuid(
        self,
        device: str,
    ) -> str:
        value = self.run_command(
            [
                "blkid",
                "-s",
                "UUID",
                "-o",
                "value",
                device,
            ]
        ).strip()

        if not value:
            raise InstallError(
                f"Could not determine UUID for {device}."
            )

        return value

    def configure_fstab(
        self,
        boot: str,
        root: str,
        mapped_root=None,
    ):
        filesystem = str(
            self.state.get(
                "filesystem",
                "ext4",
            )
        ).lower()

        filesystem_root = (
            mapped_root or root
        )

        root_uuid = self.block_uuid(
            filesystem_root
        )

        boot_uuid = self.block_uuid(
            boot
        )

        lines = [
            f"UUID={root_uuid} / "
            f"{filesystem} defaults,noatime 0 1",
            f"UUID={boot_uuid} /boot "
            "vfat umask=0077 0 2",
        ]

        self.write_file(
            self.target / "etc/fstab",
            "\n".join(lines) + "\n",
        )

        if self.encryption_enabled():
            luks_uuid = self.block_uuid(
                root
            )

            self.write_file(
                self.target /
                "etc/crypttab",
                "mulios-root "
                f"UUID={luks_uuid} "
                "none luks\n",
            )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def configure_identity(self):
        hostname = str(
            self.state.get(
                "hostname",
                "mulios",
            )
        ).strip()

        locale = str(
            self.state.get(
                "locale",
                "en_US.UTF-8",
            )
        ).strip()

        keyboard = str(
            self.state.get(
                "keyboard_layout",
                "us",
            )
        ).strip()

        timezone = str(
            self.state.get(
                "timezone",
                "UTC",
            )
        ).strip()

        # --------------------------------------------------------------
        # Validate hostname
        # --------------------------------------------------------------

        if not hostname:
            hostname = "mulios"

        if len(hostname) > 253:
            raise InstallError(
                "Hostname is too long."
            )

        if not re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?",
            hostname,
        ):
            raise InstallError(
                f"Invalid hostname: {hostname}"
            )

        # --------------------------------------------------------------
        # Validate locale
        # --------------------------------------------------------------

        if not locale:
            raise InstallError(
                "No locale was selected."
            )

        if not re.fullmatch(
            r"[A-Za-z0-9_.@+-]+",
            locale,
        ):
            raise InstallError(
                f"Invalid locale: {locale}"
            )

        # --------------------------------------------------------------
        # Validate keyboard layout
        # --------------------------------------------------------------

        if not keyboard:
            keyboard = "us"

        if not re.fullmatch(
            r"[A-Za-z0-9_-]+",
            keyboard,
        ):
            raise InstallError(
                f"Invalid keyboard layout: {keyboard}"
            )

        # --------------------------------------------------------------
        # Validate timezone
        # --------------------------------------------------------------

        if not timezone:
            timezone = "UTC"

        if timezone.startswith("/") or ".." in Path(timezone).parts:
            raise InstallError(
                f"Invalid timezone: {timezone}"
            )

        zoneinfo_root = (
            self.target /
            "usr/share/zoneinfo"
        )

        zoneinfo = (
            zoneinfo_root /
            timezone
        )

        if not zoneinfo.is_file():
            raise InstallError(
                f"Timezone is not available in the target system: "
                f"{timezone}"
            )

        # --------------------------------------------------------------
        # Host identity
        # --------------------------------------------------------------

        self.write_file(
            self.target / "etc/hostname",
            hostname + "\n",
        )

        hosts = (
            "127.0.0.1 localhost\n"
            "::1 localhost\n"
            f"127.0.1.1 {hostname}\n"
        )

        self.write_file(
            self.target / "etc/hosts",
            hosts,
        )

        # --------------------------------------------------------------
        # Locale configuration
        # --------------------------------------------------------------

        locale_conf = (
            f"LANG={locale}\n"
        )

        self.write_file(
            self.target / "etc/locale.conf",
            locale_conf,
        )

        locale_gen = (
            self.target /
            "etc/locale.gen"
        )

        if not locale_gen.exists():
            raise InstallError(
                "Target system is missing /etc/locale.gen."
            )

        text = locale_gen.read_text(
            encoding="utf-8",
            errors="replace",
        )

        locale_found = False
        output = []

        locale_pattern = re.compile(
            rf"^\s*#?\s*{re.escape(locale)}(?:\s|$)"
        )

        for line in text.splitlines():
            if locale_pattern.match(line):
                output.append(locale)
                locale_found = True
            else:
                output.append(line)

        if not locale_found:
            raise InstallError(
                f"Locale {locale} is not available "
                "in /etc/locale.gen."
            )

        locale_gen.write_text(
            "\n".join(output) + "\n",
            encoding="utf-8",
        )

        # --------------------------------------------------------------
        # Keyboard configuration
        # --------------------------------------------------------------

        self.write_file(
            self.target / "etc/vconsole.conf",
            f"KEYMAP={keyboard}\n",
        )

        # --------------------------------------------------------------
        # Timezone
        # --------------------------------------------------------------

        localtime = (
            self.target /
            "etc/localtime"
        )

        if localtime.exists() or localtime.is_symlink():
            localtime.unlink()

        localtime.symlink_to(
            Path(
                "/usr/share/zoneinfo"
            ) / timezone
        )

        # --------------------------------------------------------------
        # Generate locale and synchronize hardware clock
        # --------------------------------------------------------------

        self.log(
            f"Configuring locale: {locale}"
        )

        self.chroot(
            ["locale-gen"]
        )

        self.log(
            f"Configuring timezone: {timezone}"
        )

        self.chroot(
            [
                "hwclock",
                "--systohc",
            ],
            check=False,
        )

        self.progress.emit(50)

    # ------------------------------------------------------------------
    # Pacman / mirrors
    # ------------------------------------------------------------------

    def configure_mirrors(self):
        mirror_region = str(
            self.state.get(
                "mirror_region",
                "Worldwide",
            )
        ).strip()

        mirrorlist = (
            self.target /
            "etc/pacman.d/mirrorlist"
        )

        if not mirrorlist.parent.exists():
            mirrorlist.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        # Do not inherit the ISO's huge generated mirrorlist. A long list
        # of mirrors makes installation fragile when DNS or individual
        # mirrors are unavailable. Use a small curated HTTPS set instead.
        #
        # These mirrors are currently listed as active by Arch Linux's
        # official mirror-status service. Keep multiple geographic options
        # so one unavailable host cannot stop installation.
        mirrors = [
            "https://fastly.mirror.pkgbuild.com/\\$repo/os/\\$arch",
            "https://mirror.cyberbits.eu/archlinux/\\$repo/os/\\$arch",
            "https://mirror.thekinrar.fr/archlinux/\\$repo/os/\\$arch",
            "https://berlin.mirror.pkgbuild.com/\\$repo/os/\\$arch",
        ]

        mirror_text = (
            "# MuliOS installer mirrorlist\\n"
            "# Curated HTTPS mirrors; generated dynamically by the installer.\\n"
            + "\\n".join(
                f"Server = {mirror}"
                for mirror in mirrors
            )
            + "\\n"
        )

        mirrorlist.write_text(
            mirror_text,
            encoding="utf-8",
        )

        self.log(
            "Configured curated Arch Linux HTTPS mirrors."
        )

        if mirror_region:
            self.log(
                f"Requested mirror region: {mirror_region}; "
                "using curated HTTPS fallback mirrors for reliability."
            )

    def ensure_active_mirror(
        self,
        mirrorlist: Path,
    ):
        text = mirrorlist.read_text(
            encoding="utf-8",
            errors="replace",
        )

        if re.search(
            r"(?m)^\s*Server\s*=",
            text,
        ):
            return

        raise InstallError(
            "No usable Arch Linux mirror was configured."
        )

    def configure_multilib(self):
        enabled = bool(
            self.state.get(
                "enable_multilib",
                True,
            )
        )

        pacman_conf = (
            self.target /
            "etc/pacman.conf"
        )

        if not pacman_conf.exists():
            raise InstallError(
                "Target /etc/pacman.conf is missing."
            )

        text = pacman_conf.read_text(
            encoding="utf-8",
            errors="replace",
        )

        lines = text.splitlines()

        output = []
        in_multilib = False

        for line in lines:
            stripped = line.strip()

            if stripped in (
                "[multilib]",
                "#[multilib]",
            ):
                in_multilib = True

                if enabled:
                    output.append(
                        "[multilib]"
                    )
                else:
                    output.append(
                        "#[multilib]"
                    )

                continue

            if (
                in_multilib
                and stripped.startswith(
                    "Include"
                )
            ):
                if enabled:
                    output.append(
                        re.sub(
                            r"^\s*#\s*",
                            "",
                            line,
                        )
                    )
                else:
                    if line.lstrip().startswith(
                        "#"
                    ):
                        output.append(line)
                    else:
                        output.append(
                            "#" + line
                        )

                in_multilib = False
                continue

            if (
                in_multilib
                and stripped.startswith(
                    "#Include"
                )
            ):
                if enabled:
                    output.append(
                        line.replace(
                            "#Include",
                            "Include",
                            1,
                        )
                    )
                else:
                    output.append(line)

                in_multilib = False
                continue

            output.append(line)

        text = (
            "\n".join(output) +
            "\n"
        )

        downloads = self.state.get(
            "parallel_downloads",
            5,
        )

        try:
            downloads = max(
                1,
                min(
                    20,
                    int(downloads),
                ),
            )
        except (
            TypeError,
            ValueError,
        ):
            downloads = 5

        text = re.sub(
            r"(?m)^#?\s*ParallelDownloads\s*=.*$",
            f"ParallelDownloads = {downloads}",
            text,
        )

        if not re.search(
            r"(?m)^ParallelDownloads\s*=",
            text,
        ):
            text += (
                "\n"
                "[options]\n"
                f"ParallelDownloads = {downloads}\n"
            )

        pacman_conf.write_text(
            text,
            encoding="utf-8",
        )

        self.configure_mirrors()

    def prepare_network(self):
        self.log(
            "Preparing target network configuration..."
        )

        pacman_conf = self.target / "etc/pacman.conf"

        # The ISO build uses a host-local [mulios] repository to install
        # custom packages. That repository must never survive into the
        # installed system.
        if pacman_conf.exists():
            backup_dir = (
                self.target /
                "var/lib/mulios-installer/pacman-backup"
            )
            backup_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                pacman_conf,
                backup_dir / "pacman.conf",
            )

            pacman_text = pacman_conf.read_text(
                encoding="utf-8",
                errors="replace",
            )

            pacman_text = re.sub(
                r"(?ms)^\[mulios\]\s*.*?(?=^\[|\Z)",
                "",
                pacman_text,
            )

            if re.search(
                r"(?mi)^\s*Server\s*=\s*file:///root/MuliOS-Arch/profile/packages\s*$",
                pacman_text,
            ) or re.search(
                r"(?mi)^\[mulios\]\s*$",
                pacman_text,
            ):
                raise InstallError(
                    "Build-only [mulios] repository remained in target "
                    "/etc/pacman.conf after cleanup."
                )

            pacman_conf.write_text(
                pacman_text,
                encoding="utf-8",
            )

            self.log(
                "Removed build-only [mulios] repository."
            )

        resolv = self.target / "etc/resolv.conf"

        if resolv.exists() or resolv.is_symlink():
            resolv.unlink()

        nameservers = []

        for source in (
            Path("/run/systemd/resolve/resolv.conf"),
            Path("/etc/resolv.conf"),
        ):
            if not source.exists():
                continue

            try:
                source_text = source.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            for line in source_text.splitlines():
                match = re.match(
                    r"^\s*nameserver\s+([^\s#]+)",
                    line,
                )

                if not match:
                    continue

                address = match.group(1).strip()

                if address in (
                    "127.0.0.1",
                    "127.0.0.53",
                    "::1",
                ):
                    continue

                if address not in nameservers:
                    nameservers.append(address)

            if nameservers:
                break

        for address in (
            "1.1.1.1",
            "8.8.8.8",
            "9.9.9.9",
        ):
            if address not in nameservers:
                nameservers.append(address)

        resolv.write_text(
            "# Generated by MuliOS Native Installer.\\n"
            + "".join(
                f"nameserver {address}\\n"
                for address in nameservers[:4]
            ),
            encoding="utf-8",
        )

        self.log(
            "Configured target DNS nameservers: "
            + ", ".join(nameservers[:4])
        )

        # Network is optional. Never abort an installation just because
        # the live environment has no Internet connection.
        dns_ok = self.chroot(
            ["getent", "hosts", "archlinux.org"],
            check=False,
        )

        self.network_available = bool(dns_ok.strip())

        if self.network_available:
            self.log("Internet access detected.")
            self.configure_multilib()
        else:
            self.log(
                "No Internet connection detected. "
                "Continuing in offline installation mode."
            )

    def pacman_install(
        self,
        packages,
    ):
        packages = [
            str(package).strip()
            for package in packages
            if str(package).strip()
        ]

        if not packages:
            return

        self.prepare_network()

        def offline_package_check():
            missing = []

            for package in packages:
                result = self.chroot(
                    ["pacman", "-Q", package],
                    check=False,
                )

                if result.strip():
                    self.log(
                        f"Offline mode: {package} is already installed."
                    )
                else:
                    missing.append(package)

            if missing:
                self.log(
                    "Offline mode: these optional packages are not "
                    "available locally and will be skipped: "
                    + " ".join(missing)
                )

            self.pacman_synced = True

        # Internet is optional. If the live session has no Internet,
        # continue using the packages already present in the ISO.
        if not self.network_available:
            offline_package_check()
            return

        if not self.pacman_synced:
            self.log("Preparing target pacman keyring...")

            self.chroot(["mkdir", "-p", "/etc/pacman.d/gnupg"])
            self.chroot(["chmod", "700", "/etc/pacman.d/gnupg"])
            self.chroot(["chown", "-R", "root:root", "/etc/pacman.d/gnupg"])

            self.log("Initializing target pacman keyring...")
            self.chroot(["pacman-key", "--init"])
            self.chroot(["pacman-key", "--populate", "archlinux"])

            self.log("Backing up pacman state before recovery...")
            self.chroot(
                [
                    "bash",
                    "-c",
                    "mkdir -p /var/lib/mulios-installer/pacman-backup && "
                    "cp -a /var/lib/pacman/sync "
                    "/var/lib/mulios-installer/pacman-backup/sync-backup "
                    "2>/dev/null || true",
                ],
                check=False,
            )

            self.log("Refreshing Arch Linux package databases...")

            refresh = self.chroot(
                ["pacman", "-Syy", "--noconfirm"],
                check=False,
            )

            refresh_failed = (
                not refresh.strip()
                or "error:" in refresh.lower()
                or "failed to retrieve" in refresh.lower()
                or "could not resolve" in refresh.lower()
                or "failed retrieving" in refresh.lower()
            )

            if refresh_failed:
                self.log(
                    "Pacman database refresh failed. "
                    "Cleaning the sync database and retrying once..."
                )

                self.chroot(
                    [
                        "bash",
                        "-c",
                        "find /var/lib/pacman/sync -mindepth 1 "
                        "-maxdepth 1 -type f -delete",
                    ],
                    check=False,
                )

                refresh = self.chroot(
                    ["pacman", "-Syy", "--noconfirm"],
                    check=False,
                )

                refresh_failed = (
                    not refresh.strip()
                    or "error:" in refresh.lower()
                    or "failed to retrieve" in refresh.lower()
                    or "could not resolve" in refresh.lower()
                    or "failed retrieving" in refresh.lower()
                )

            if refresh_failed:
                self.log(
                    "Pacman cannot reach the configured mirrors. "
                    "Falling back to offline installation. "
                    "Packages already present in the ISO will be kept."
                )
                self.network_available = False
                offline_package_check()
                return

            self.log("Installing/updating archlinux-keyring...")

            keyring = self.chroot(
                [
                    "pacman",
                    "-S",
                    "--needed",
                    "--noconfirm",
                    "archlinux-keyring",
                ],
                check=False,
            )

            if "error:" in keyring.lower():
                self.log(
                    "Keyring update failed. Reinitializing the target "
                    "keyring and retrying once..."
                )

                self.chroot(
                    [
                        "bash",
                        "-c",
                        "find /etc/pacman.d/gnupg -mindepth 1 "
                        "-maxdepth 1 -exec rm -rf {} +",
                    ],
                    check=False,
                )

                self.chroot(["pacman-key", "--init"])
                self.chroot(["pacman-key", "--populate", "archlinux"])

                keyring_retry = self.chroot(
                    [
                        "pacman",
                        "-S",
                        "--needed",
                        "--noconfirm",
                        "archlinux-keyring",
                    ],
                    check=False,
                )

                if "error:" in keyring_retry.lower():
                    self.log(
                        "Arch Linux keyring could not be updated. "
                        "Continuing with the keyring already present in "
                        "the live ISO."
                    )

            self.log(
                "Synchronizing target package databases and "
                "upgrading the target system..."
            )

            upgrade = self.chroot(
                ["pacman", "-Syu", "--noconfirm"],
                check=False,
            )

            if "error:" in upgrade.lower():
                self.log(
                    "Target package upgrade failed. "
                    "Continuing installation without the upgrade."
                )

            self.pacman_synced = True

        self.log(
            "Installing packages: " +
            " ".join(packages)
        )

        package_result = self.chroot(
            [
                "pacman",
                "-S",
                "--needed",
                "--noconfirm",
                *packages,
            ],
            check=False,
        )

        if "error:" in package_result.lower():
            self.log(
                "Some requested packages could not be installed. "
                "Continuing with the packages already available in "
                "the ISO."
            )

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def create_user(self):
        username = str(
            self.state.get(
                "username",
                "",
            )
        ).strip()

        password = str(
            self.state.get(
                "user_password",
                "",
            )
        )

        if not username:
            raise InstallError(
                "Username cannot be empty."
            )

        if len(username) > 32:
            raise InstallError(
                "Username cannot be longer than 32 characters."
            )

        if not re.fullmatch(
            r"[a-z_][a-z0-9_-]*[$]?",
            username,
        ):
            raise InstallError(
                f"Invalid username: {username}. "
                "Use lowercase letters, numbers, underscores, "
                "and hyphens; the first character must be a letter "
                "or underscore."
            )

        if username in {
            "root",
            "daemon",
            "bin",
            "sys",
            "sync",
            "games",
            "man",
            "lp",
            "mail",
            "news",
            "uucp",
            "proxy",
            "www-data",
            "backup",
            "list",
            "irc",
            "nobody",
            "systemd-network",
            "systemd-resolve",
            "dbus",
        }:
            raise InstallError(
                f"Username is reserved: {username}"
            )

        if password:
            self.log(
                f"Creating user account: {username}"
            )
        else:
            self.log(
                f"Creating user account: {username} with no password (warning accepted)."
            )

        self.chroot(
            [
                "useradd",
                "-m",
                "-G",
                "wheel,audio,video,network",
                "-s",
                "/bin/bash",
                username,
            ]
        )

        if password:
            self.chroot(
                ["chpasswd"],
                input_text=(
                    f"{username}:{password}\n"
                ),
            )
        else:
            self.chroot(
                ["passwd", "-d", username],
            )

        sudoers = (
            self.target /
            "etc/sudoers.d/mulios-wheel"
        )

        if password:
            sudoers_text = "%wheel ALL=(ALL:ALL) ALL\n"
        else:
            # An account with no password cannot authenticate through sudo's
            # normal password prompt. Explicitly allow wheel sudo without a
            # password when the user chose no password.
            sudoers_text = "%wheel ALL=(ALL:ALL) NOPASSWD: ALL\n"

        self.write_file(
            sudoers,
            sudoers_text,
            mode=0o440,
        )

        self.configure_installed_plasma(username)
        self.progress.emit(60)

    def configure_installed_plasma(self, username):
        """Seed the installed user's Plasma session from the live MuliOS session."""
        home = self.target / "home" / username
        config = home / ".config"
        config.mkdir(parents=True, exist_ok=True)

        live_config = Path("/home/liveuser/.config")
        files = [
            "kdeglobals",
            "kwinrc",
            "plasmarc",
            "plasma-org.kde.plasma.desktop-appletsrc",
            "kcminputrc",
            "kglobalshortcutsrc",
            "kscreenlockerrc",
        ]

        copied = []
        if live_config.is_dir():
            for name in files:
                source = live_config / name
                destination = config / name
                if source.is_file():
                    shutil.copy2(source, destination)
                    copied.append(name)

        # Force the modern Plasma/Breeze lock-screen implementation while
        # keeping the MuliOS ROUNDED-DARK color scheme.
        kdeglobals = config / "kdeglobals"
        kde_text = kdeglobals.read_text(encoding="utf-8", errors="replace") if kdeglobals.exists() else ""
        if "[KDE]" not in kde_text:
            kde_text += "\\n[KDE]\\n"
        if re.search(r"(?m)^LookAndFeelPackage=", kde_text):
            kde_text = re.sub(
                r"(?m)^LookAndFeelPackage=.*$",
                "LookAndFeelPackage=org.kde.breeze.desktop",
                kde_text,
            )
        else:
            kde_text += "LookAndFeelPackage=org.kde.breeze.desktop\\n"
        kdeglobals.write_text(kde_text.rstrip() + "\\n", encoding="utf-8")

        # The live ISO does not need the installed-session splash. Disable
        # the KDE splash explicitly for the installed user.
        ksplashrc = config / "ksplashrc"
        ksplashrc.write_text(
            "[KSplash]\\n"
            "Engine=none\\n"
            "Theme=None\\n",
            encoding="utf-8",
        )

        # Force the Breeze lock-screen implementation explicitly.
        kscreenlockerrc = config / "kscreenlockerrc"
        kscreenlockerrc.write_text(
            "[Greeter]\\n"
            "Theme=org.kde.breeze.desktop\\n",
            encoding="utf-8",
        )

        self.chroot([
            "chown",
            "-R",
            f"{username}:{username}",
            f"/home/{username}/.config",
        ])

        if copied:
            self.log(
                "Applied live MuliOS Plasma configuration to "
                f"installed user: {', '.join(copied)}"
            )
        else:
            self.log(
                "Live Plasma user configuration was unavailable; "
                "installed-user defaults were created."
            )

        self.log("Configured modern Plasma lock screen and disabled KDE splash screen.")

        # Plasma wallpaper state is session-owned. The live ISO already
        # ships the authoritative helper under /usr/local/bin; keep that
        # helper intact so Plasma 6 is configured through its D-Bus scripting
        # API on first login.
        wallpaper_script = self.target / "usr/local/bin/mulios-apply-wallpaper"
        if wallpaper_script.is_file():
            os.chmod(wallpaper_script, 0o755)
        else:
            self.log("WARNING: MuliOS wallpaper helper is missing from the target filesystem.")

        wallpaper_autostart = self.target / "etc/xdg/autostart/mulios-wallpaper.desktop"
        wallpaper_autostart.parent.mkdir(parents=True, exist_ok=True)
        wallpaper_autostart.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=MuliOS Wallpaper\n"
            "Exec=/usr/local/bin/mulios-wallpaper-autostart\n"
            "OnlyShowIn=KDE;\n"
            "X-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )

        # The installed system must not contain the live installer or
        # a stale desktop shortcut that points at the removed installer.
        installed_desktop_shortcut = home / "Desktop" / "mulios-installer.desktop"
        if installed_desktop_shortcut.exists() or installed_desktop_shortcut.is_symlink():
            try:
                installed_desktop_shortcut.unlink()
                self.log("Removed live installer shortcut from installed user's Desktop.")
            except FileNotFoundError:
                pass

        for installer_path in (
            self.target / "opt/mulios-installer",
            self.target / "usr/local/bin/mulios-installer",
            self.target / "usr/share/applications/mulios-installer.desktop",
            self.target / "etc/xdg/autostart/mulios-installer.desktop",
        ):
            if installer_path.is_dir() and not installer_path.is_symlink():
                shutil.rmtree(installer_path, ignore_errors=True)
            elif installer_path.exists() or installer_path.is_symlink():
                try:
                    installer_path.unlink()
                except FileNotFoundError:
                    pass

        # Never carry the live-session autologin into the installed system.
        autologin = self.target / "etc/sddm.conf.d/autologin.conf"
        if autologin.exists() or autologin.is_symlink():
            autologin.unlink()

        self.log("Removed installer files and live-session autologin from installed system.")

    def configure_root_account(self):
        password = str(
            self.state.get(
                "root_password",
                "",
            )
        )

        if password:
            self.log(
                "Configuring root password..."
            )

            self.chroot(
                ["chpasswd"],
                input_text=(
                    f"root:{password}\n"
                ),
            )
        else:
            self.log(
                "Disabling direct root login..."
            )

            self.chroot(
                [
                    "passwd",
                    "-l",
                    "root",
                ],
                check=False,
            )

    # ------------------------------------------------------------------
    # Kernel
    # ------------------------------------------------------------------

    def configure_kernel(self):
        # MuliOS ships its own kernel in the ISO. The live kernel is outside
        # the airootfs, so rsync cannot copy it into the installed /boot.
        # The previous installer selected the generic Arch "linux" package;
        # in offline installs that package is skipped, leaving an initramfs
        # without its matching kernel. Install the bundled MuliOS kernel
        # directly from the live ISO instead.
        kernel = str(
            self.state.get(
                "kernel",
                "linux-mulios-generic",
            )
        ).strip().lower()

        allowed = {
            "linux": "linux-mulios-generic",
            "linux-mulios-generic": "linux-mulios-generic",
        }

        package = allowed.get(kernel)

        if package is None:
            raise InstallError(
                f"Unsupported kernel selection: {kernel}"
            )

        self.kernel_package = package
        kernel_name = "vmlinuz-linux-mulios-generic"
        kernel_destination = self.target / "boot" / kernel_name

        candidates = [
            Path("/run/archiso/boot/x86_64") / kernel_name,
            Path("/run/archiso/boot/amd64") / kernel_name,
            Path("/run/live/boot/x86_64") / kernel_name,
            Path("/run/live/boot/amd64") / kernel_name,
        ]

        source = next(
            (path for path in candidates if path.is_file()),
            None,
        )

        if source is None:
            # Some archiso layouts expose the boot tree through a mounted
            # ISO path. Search only the known live-media roots.
            for root in (
                Path("/run/archiso"),
                Path("/run/live"),
            ):
                if not root.is_dir():
                    continue
                matches = list(root.glob(
                    "**/vmlinuz-linux-mulios-generic"
                ))
                if matches:
                    source = matches[0]
                    break

        if source is None:
            raise InstallError(
                "Could not locate the bundled MuliOS kernel "
                "vmlinuz-linux-mulios-generic on the live media."
            )

        self.log(
            f"Installing bundled MuliOS kernel from {source}"
        )
        kernel_destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        shutil.copy2(source, kernel_destination)
        os.chmod(kernel_destination, 0o644)

        # The live ISO carries ArchISO-specific mkinitcpio configuration.
        # It must never be used by the installed system.
        self.configure_installed_mkinitcpio()

        # Keep firmware and encryption support from the live environment;
        # these are optional when offline and will be retained if already
        # present in the copied root filesystem.
        packages = ["linux-firmware"]
        if self.encryption_enabled():
            packages.append("cryptsetup")
        self.pacman_install(packages)

        self.log(
            "Bundled MuliOS kernel installed successfully."
        )

    def kernel_paths(self):
        return (
            "vmlinuz-linux-mulios-generic",
            "initramfs-linux-mulios-generic.img",
        )

    def configure_installed_mkinitcpio(self):
        config_dir = self.target / "etc/mkinitcpio.conf.d"
        config_dir.mkdir(parents=True, exist_ok=True)

        archiso_config = config_dir / "archiso.conf"
        if archiso_config.exists() or archiso_config.is_symlink():
            archiso_config.unlink()

        hooks = [
            "base",
            "udev",
            "autodetect",
            "microcode",
            "modconf",
            "kms",
            "keyboard",
            "keymap",
            "consolefont",
            "block",
            "filesystems",
            "fsck",
        ]

        if self.encryption_enabled():
            hooks.insert(-2, "encrypt")

        self.write_file(
            self.target / "etc/mkinitcpio.conf",
            "\n".join([
                "# MuliOS installed-system initramfs configuration",
                "",
                "MODULES=(virtio_pci virtio_blk virtio_scsi)",
                "BINARIES=()",
                "FILES=()",
                "HOOKS=(" + " ".join(hooks) + ")",
                'COMPRESSION="zstd"',
                "",
            ]),
        )

        preset = self.target / "etc/mkinitcpio.d/linux-mulios-generic.preset"
        self.write_file(
            preset,
            """# mkinitcpio preset file for linux-mulios-generic

ALL_config="/etc/mkinitcpio.conf"
ALL_kver="/usr/lib/modules/7.2.3-mulios-generic/vmlinuz"

PRESETS=('default')

default_image="/boot/initramfs-linux-mulios-generic.img"
""",
        )

        self.log(
            "Replaced ArchISO mkinitcpio configuration with the installed MuliOS configuration."
        )
        self.log(
            "Installed-system mkinitcpio hooks: " + " ".join(hooks)
        )

    # ------------------------------------------------------------------
    # Desktop
    # ------------------------------------------------------------------

    def configure_desktop(self):
        self.log("Installing KDE Plasma...")
        
        for path in (
            self.target / "etc/sddm.conf",
            self.target / "etc/sddm.conf.d/autologin.conf",
        ):
            if path.exists() or path.is_symlink():
                path.unlink()

        for manager in ("sddm", "lightdm", "gdm"):
            self.chroot(["systemctl", "disable", manager], check=False)

        self.pacman_install([
            "plasma-desktop",
            "sddm",
            "dolphin",
        ])

        # configure_desktop() starts from the installed package set, so write
        # the final SDDM configuration after the package installation step.
        sddm_conf = self.target / "etc/sddm.conf"
        sddm_conf.parent.mkdir(parents=True, exist_ok=True)
        sddm_conf.write_text(
            "[Theme]\n"
            "Current=mulios\n",
            encoding="utf-8",
        )

        # The live session must never be the installed login user.
        autologin = self.target / "etc/sddm.conf.d/autologin.conf"
        if autologin.exists() or autologin.is_symlink():
            autologin.unlink()

        self.chroot(["systemctl", "enable", "sddm"])
        self.progress.emit(70)

    # ------------------------------------------------------------------
    # Extra packages
    # ------------------------------------------------------------------

    def install_extra_packages(self):
        packages = self.state.get(
            "extra_packages",
            [],
        )

        if isinstance(
            packages,
            str,
        ):
            packages = packages.split()

        self.pacman_install(
            packages
        )

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------

    def profile_packages(self):
        profile = str(
            self.state.get(
                "profile",
                "generic",
            )
        ).strip().lower()

        profiles = {
            "gaming": [
                "steam",
                "gamemode",
                "gamescope",
            ],
            "code": [
                "git",
                "base-devel",
                "python",
                "gcc",
                "clang",
            ],
            "ai": [
                "git",
                "python",
                "python-pip",
            ],
            "school": [
                "libreoffice-fresh",
                "evince",
            ],
            "privacy": [
                "firejail",
                "tor",
            ],
            "generic": [],
        }

        return profile, profiles.get(
            profile
        )

    def configure_profile(self):
        profile, packages = (
            self.profile_packages()
        )

        self.log(
            f"Configuring MuliOS profile: "
            f"{profile}"
        )

        if profile == "gaming":
            self.log(
                "Gaming profile requires multilib."
            )

            self.state[
                "enable_multilib"
            ] = True

            self.configure_multilib()

        if packages:
            self.pacman_install(
                packages
            )

        self.write_file(
            self.target /
            "var/lib/mupdate/"
            "initial-profile",
            profile + "\n",
        )

    # ------------------------------------------------------------------
    # MUpdate
    # ------------------------------------------------------------------

    def configure_mupdate(self):
        if bool(
            self.state.get(
                "skip_mupdate",
                False,
            )
        ):
            self.log(
                "Installer requested MUpdate skip."
            )
            return

        candidates = [
            Path(
                "/opt/mulios-installer/mupdate"
            ),
            Path(
                "/opt/mupdate"
            ),
            Path(
                "/usr/local/bin/mupdate"
            ),
            Path(__file__).resolve().parent.parent /
            "mupdate",
        ]

        source = None

        for candidate in candidates:
            if candidate.exists():
                source = candidate
                break

        if source is None:
            self.log(
                "Bundled MUpdate executable was not found."
            )
            return

        destination = (
            self.target /
            "usr/local/bin/mupdate"
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

        os.chmod(
            destination,
            0o755,
        )

        self.log(
            f"Installed MUpdate from {source}"
        )

    # ------------------------------------------------------------------
    # Swap
    # ------------------------------------------------------------------

    def swap_enabled(self):
        return bool(
            self.state.get(
                "enable_swap",
                False,
            )
        )

    def configure_swap(self):
        if not self.swap_enabled():
            self.log(
                "Swap disabled."
            )
            return

        swapfile = (
            self.target /
            "swapfile"
        )

        filesystem = str(
            self.state.get(
                "filesystem",
                "ext4",
            )
        ).lower()

        self.log(
            f"Creating {SWAP_SIZE} swapfile..."
        )

        if filesystem == "btrfs":
            self.run_command(
                [
                    "touch",
                    str(swapfile),
                ]
            )

            self.run_command(
                [
                    "chattr",
                    "+C",
                    str(swapfile),
                ]
            )

        self.run_command(
            [
                "fallocate",
                "-l",
                SWAP_SIZE,
                str(swapfile),
            ]
        )

        self.run_command(
            [
                "chmod",
                "600",
                str(swapfile),
            ]
        )

        self.run_command(
            [
                "mkswap",
                str(swapfile),
            ]
        )

        with (
            self.target /
            "etc/fstab"
        ).open(
            "a",
            encoding="utf-8",
        ) as f:
            f.write(
                "/swapfile none swap "
                "defaults 0 0\n"
            )

        self.log(
            "Swapfile configured."
        )

    # ------------------------------------------------------------------
    # Initramfs encryption
    # ------------------------------------------------------------------

    def configure_initramfs_encryption(self):
        if not self.encryption_enabled():
            return

        conf = (
            self.target /
            "etc/mkinitcpio.conf"
        )

        if not conf.exists():
            raise InstallError(
                "mkinitcpio.conf is missing."
            )

        text = conf.read_text(
            encoding="utf-8",
            errors="replace",
        )

        match = re.search(
            r"(?m)^HOOKS=\(([^)]*)\)",
            text,
        )

        if not match:
            raise InstallError(
                "Could not find HOOKS in mkinitcpio.conf."
            )

        existing_hooks = match.group(1).split()

        # Keep the existing hook configuration intact and only add
        # the hooks required for encrypted-root boot.
        if "systemd" in existing_hooks:
            required_hooks = [
                "systemd",
                "keyboard",
                "block",
                "sd-encrypt",
                "filesystems",
            ]
        else:
            required_hooks = [
                "udev",
                "keyboard",
                "keymap",
                "block",
                "encrypt",
                "filesystems",
            ]

        hooks = list(existing_hooks)

        for hook in required_hooks:
            if hook not in hooks:
                hooks.append(hook)

        # Remove the encryption hook that belongs to the other initramfs
        # framework. This prevents both encrypt and sd-encrypt from being
        # enabled simultaneously.
        if "systemd" in hooks:
            hooks = [
                hook
                for hook in hooks
                if hook != "encrypt"
            ]

            if "sd-encrypt" not in hooks:
                hooks.append("sd-encrypt")

        else:
            hooks = [
                hook
                for hook in hooks
                if hook != "sd-encrypt"
            ]

            if "encrypt" not in hooks:
                hooks.append("encrypt")

        replacement = (
            "HOOKS=(" +
            " ".join(hooks) +
            ")"
        )

        text = (
            text[:match.start()] +
            replacement +
            text[match.end():]
        )

        conf.write_text(
            text,
            encoding="utf-8",
        )

        self.log(
            "Configured encrypted-root mkinitcpio hooks."
        )
        self.log(
            "Final HOOKS=(" +
            " ".join(hooks) +
            ")"
        )

    # ------------------------------------------------------------------
    # Kernel command line
    # ------------------------------------------------------------------

    def kernel_cmdline(self):
        root_uuid = self.block_uuid(
            self.mapped_root or
            self.root_partition
        )

        # grub-mkconfig supplies the root=UUID argument itself. Adding the
        # root UUID here causes duplicate root= arguments in generated GRUB.
        args = []

        if self.encryption_enabled():
            luks_uuid = self.block_uuid(
                self.root_partition
            )

            conf = (
                self.target /
                "etc/mkinitcpio.conf"
            )

            text = conf.read_text(
                encoding="utf-8",
                errors="replace",
            )

            if "sd-encrypt" in text:
                args.insert(
                    0,
                    f"rd.luks.name="
                    f"{luks_uuid}=mulios-root",
                )
            else:
                args.insert(
                    0,
                    "cryptdevice="
                    f"UUID={luks_uuid}:"
                    "mulios-root",
                )

        return " ".join(args)

    # ------------------------------------------------------------------
    # Bootloader
    # ------------------------------------------------------------------

    def configure_grub(self):
        self.log("Installing GRUB...")

        self.pacman_install([
            "grub",
            "efibootmgr",
            "os-prober",
        ])

        # Make UEFI NVRAM available inside the target before grub-install and
        # efibootmgr run. arch-chroot does not guarantee that efivarfs is
        # mounted at /sys/firmware/efi/efivars in every live environment.
        # Without it, GRUB may be installed to the EFI partition but MuliOS
        # will not appear in the firmware boot selector.
        efivars = self.target / "sys/firmware/efi/efivars"
        efivars.mkdir(parents=True, exist_ok=True)

        efivars_fstype = self.run_command(
            ["findmnt", "-n", "-o", "FSTYPE", str(efivars)],
            check=False,
        ).strip()

        if efivars_fstype != "efivarfs":
            live_efivars = Path(
                "/sys/firmware/efi/efivars"
            )

            if not live_efivars.is_dir():
                raise InstallError(
                    "UEFI efivarfs is unavailable in the live environment. "
                    "Cannot create the MuliOS firmware boot entry."
                )

            self.run_command([
                "mount",
                "--bind",
                str(live_efivars),
                str(efivars),
            ])

        if not self.run_command(
            ["mountpoint", "-q", str(efivars)],
            check=False,
        ):
            raise InstallError(
                "Could not mount UEFI efivarfs in the installed system. "
                "Cannot create the MuliOS firmware boot entry."
            )

        self.log(
            "UEFI efivarfs mounted for MuliOS NVRAM boot entry."
        )

        # Install a normal named EFI loader and create a real UEFI NVRAM
        # boot entry. The previous implementation used --no-nvram together
        # with --removable, which intentionally prevented a "MuliOS" entry
        # from being created. Firmware could still boot the fallback path, but
        # the installed system did not appear in the firmware boot selector.
        self.chroot([
            "grub-install",
            "--target=x86_64-efi",
            "--efi-directory=/boot",
            "--bootloader-id=MuliOS",
            "--recheck",
        ])

        loader = self.target / "boot/EFI/MuliOS/grubx64.efi"
        if not loader.is_file():
            raise InstallError(
                "GRUB EFI loader was not installed at "
                "/boot/EFI/MuliOS/grubx64.efi."
            )

        # Also install the standard removable-media fallback. This keeps the
        # system bootable on firmware that ignores or loses NVRAM entries.
        fallback = self.target / "boot/EFI/BOOT/BOOTX64.EFI"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(loader, fallback)

        if not fallback.is_file() or fallback.stat().st_size == 0:
            raise InstallError(
                "GRUB fallback EFI loader was not installed at "
                "/boot/EFI/BOOT/BOOTX64.EFI."
            )

        # grub-install normally creates the NVRAM entry itself. Verify it and
        # explicitly create it if firmware variables are available but the
        # entry was not created. This makes the boot selector behavior
        # deterministic instead of relying on firmware-specific behavior.
        efibootmgr_output = self.chroot(
            ["efibootmgr"],
            check=False,
        )

        if "MuliOS" not in efibootmgr_output:
            try:
                self.chroot([
                    "efibootmgr",
                    "--create",
                    "--disk",
                    self.selected_disk,
                    "--part",
                    "1",
                    "--label",
                    "MuliOS",
                    "--loader",
                    r"\EFI\MuliOS\grubx64.efi",
                    "--unicode",
                ])
            except InstallError:
                self.log(
                    "Standard UEFI NVRAM creation failed; "
                    "retrying with EDD 3 compatibility mode."
                )
                self.chroot([
                    "efibootmgr",
                    "--create",
                    "--disk",
                    self.selected_disk,
                    "--part",
                    "1",
                    "--label",
                    "MuliOS",
                    "--loader",
                    r"\EFI\MuliOS\grubx64.efi",
                    "--unicode",
                    "-e",
                    "3",
                ])

        efibootmgr_output = self.chroot(
            ["efibootmgr"],
            check=False,
        )

        if "MuliOS" not in efibootmgr_output:
            raise InstallError(
                "The MuliOS UEFI boot entry was not created. "
                "Firmware NVRAM variables are unavailable."
            )

        # Enable GRUB's OS detection so installed Linux systems on other
        # partitions are discovered and added to the boot menu.
        grub_default = self.target / "etc/default/grub"

        if grub_default.exists():
            text = grub_default.read_text(
                encoding="utf-8",
                errors="replace",
            )
        else:
            text = ""

        os_prober_setting = "GRUB_DISABLE_OS_PROBER=false"
        text = re.sub(
            r"(?m)^#?\\s*GRUB_DISABLE_OS_PROBER=.*$",
            os_prober_setting,
            text,
        )
        if not re.search(r"(?m)^GRUB_DISABLE_OS_PROBER=", text):
            text += "\\n" + os_prober_setting + "\\n"
        grub_default.write_text(text, encoding="utf-8")

        cmdline = self.kernel_cmdline()

        if grub_default.exists():
            text = grub_default.read_text(
                encoding="utf-8",
                errors="replace",
            )

            text = re.sub(
                r'(?m)^#?\s*GRUB_DISTRIBUTOR=.*$',
                'GRUB_DISTRIBUTOR="MuliOS"',
                text,
            )

            if not re.search(r'(?m)^GRUB_DISTRIBUTOR=', text):
                text += '\nGRUB_DISTRIBUTOR="MuliOS"\n'

            # Always show the GRUB menu. Arch defaults may hide the menu,
            # which makes a successful GRUB installation look like it was
            # skipped entirely.
            grub_menu_settings = {
                "GRUB_DEFAULT": "0",
                "GRUB_TIMEOUT": "5",
                "GRUB_TIMEOUT_STYLE": "menu",
            }
            for key, value in grub_menu_settings.items():
                line_value = f"{key}={value}"
                text = re.sub(
                    rf"(?m)^#?\\s*{re.escape(key)}=.*$",
                    line_value,
                    text,
                )
                if not re.search(rf"(?m)^{re.escape(key)}=", text):
                    text += f"\\n{line_value}\\n"

            line = f'GRUB_CMDLINE_LINUX_DEFAULT="{cmdline}"'
            text = re.sub(
                r'(?m)^#?\s*GRUB_CMDLINE_LINUX_DEFAULT=.*$',
                line,
                text,
            )

            if not re.search(r'(?m)^GRUB_CMDLINE_LINUX_DEFAULT=', text):
                text += f'\n{line}\n'

            grub_default.write_text(text, encoding="utf-8")

        self.chroot([
            "grub-mkconfig",
            "-o",
            "/boot/grub/grub.cfg",
        ])

        grub_cfg = self.target / "boot/grub/grub.cfg"
        if not grub_cfg.is_file() or grub_cfg.stat().st_size == 0:
            raise InstallError("GRUB configuration was not generated.")

        self.log("GRUB fallback loader and configuration verified.")

    def configure_bootloader(self):
        self.log("Bootloader is fixed to GRUB.")
        self.configure_grub()
        self.progress.emit(90)

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    def enable_services(self):
        self.log(
            "Configuring NetworkManager..."
        )

        self.pacman_install(
            ["networkmanager"]
        )

        mode = str(
            self.state.get(
                "network_mode",
                "networkmanager",
            )
        ).strip().lower()

        if mode == "copy_iso":
            source_dir = (
                Path(
                    "/etc/NetworkManager/"
                    "system-connections"
                )
            )

            target_dir = (
                self.target /
                "etc/NetworkManager/"
                "system-connections"
            )

            if source_dir.exists():
                target_dir.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                for item in source_dir.iterdir():
                    if item.is_file():
                        shutil.copy2(
                            item,
                            target_dir /
                            item.name,
                        )

                        os.chmod(
                            target_dir /
                            item.name,
                            0o600,
                        )

                self.log(
                    "Copied live NetworkManager "
                    "system connections."
                )

        self.chroot(
            [
                "systemctl",
                "enable",
                "NetworkManager",
            ]
        )

    # ------------------------------------------------------------------
    # Initramfs / finalization
    # ------------------------------------------------------------------

    def generate_initramfs(self):
        self.log(
            "Generating initramfs..."
        )

        self.chroot(
            [
                "mkinitcpio",
                "-P",
            ]
        )

        self.progress.emit(97)

    def finalize(self):
        self.log(
            "Finalizing installed MuliOS..."
        )

        machine_id = (
            self.target /
            "etc/machine-id"
        )

        if machine_id.exists():
            machine_id.unlink()

        self.chroot(
            [
                "systemd-machine-id-setup",
            ]
        )

        # Rebuild the KDE application service cache only after every
        # package and MuliOS desktop entry has been installed. The installer
        # used to leave the installed user with a cache generated before
        # Kitty, Task Manager, Credits and other .desktop files existed.
        application_entries = self.target / "usr/share/applications"
        if application_entries.is_dir():
            for desktop_file in application_entries.glob("*.desktop"):
                try:
                    os.chmod(desktop_file, 0o644)
                except OSError:
                    pass

        # Remove stale per-user KService/KMenuEdit caches inherited from the
        # live session. They must be regenerated for the installed system.
        user_cache = self.target / "home" / str(self.state.get("username", "")) / ".cache"
        if user_cache.is_dir():
            for cache_file in user_cache.glob("ksycoca*"):
                try:
                    cache_file.unlink()
                except OSError:
                    pass

        username = str(self.state.get("username", "")).strip()
        if username:
            self.chroot(
                [
                    "runuser",
                    "-u",
                    username,
                    "--",
                    "kbuildsycoca6",
                    "--noincremental",
                ],
                check=False,
            )
            self.log(
                "Rebuilt KDE application cache after installing all MuliOS applications."
            )

        self.write_file(
            self.target /
            "etc/mulios-installer-release",
            "native-installer\n",
        )

        version_file = (
            self.target /
            "etc/mulios-installer-release"
        )

        version_file.write_text(
            "native-installer\n",
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_mounts(self):
        if not self.mounts_active:
            return

        self.log("Cleaning up mounted filesystems...")

        # Unmount nested virtual filesystems first.
        cleanup_targets = [
            self.target / "dev",
            self.target / "proc",
            self.target / "sys",
            self.target / "run",
        ]

        for mountpoint in cleanup_targets:
            try:
                self.run_command(
                    [
                        "umount",
                        "-R",
                        str(mountpoint),
                    ],
                    check=False,
                )
            except Exception as exc:
                self.log(
                    f"Cleanup warning for {mountpoint}: "
                    f"{type(exc).__name__}: {exc}"
                )

        # Then unmount EFI.
        try:
            self.run_command(
                [
                    "umount",
                    str(self.target / "boot"),
                ],
                check=False,
            )
        except Exception as exc:
            self.log(
                "Cleanup warning for EFI mount: "
                f"{type(exc).__name__}: {exc}"
            )

        # Finally unmount the root filesystem.
        try:
            self.run_command(
                [
                    "umount",
                    "-R",
                    str(self.target),
                ],
                check=False,
            )
        except Exception as exc:
            self.log(
                "Cleanup warning for root mount: "
                f"{type(exc).__name__}: {exc}"
            )

        self.mounts_active = False
        self.log("Filesystem cleanup finished.")

    # ------------------------------------------------------------------
    # Main installation sequence
    # ------------------------------------------------------------------

    def run(self):
        self.initialize_log()

        try:
            self.log("=== MuliOS Native Installer ===")
            self.log("Starting installation.")
            self.log(f"Installer PID: {os.getpid()}")
            self.log(f"Running as UID: {os.geteuid()}")
            self.log(f"Target mountpoint: {self.target}")
            safe_state = dict(self.state)

            for secret_key in (
                "password",
                "user_password",
                "root_password",
                "encryption_password",
                "encryption_passphrase",
                "passphrase",
            ):
                if secret_key in safe_state:
                    safe_state[secret_key] = "<redacted>"

            self.log(
                f"Installation state: {safe_state}"
            )

            self.require_root()

            self.log("Root privilege check passed.")

            if not self.is_uefi():
                raise InstallError(
                    "MuliOS currently requires "
                    "a UEFI boot environment."
                )

            self.log("UEFI check passed.")

            disk = self.disk()

            boot, root = (
                self.partition_disk()
            )

            mapped_root = (
                self.prepare_encryption(
                    root
                )
            )

            self.format_filesystems(
                boot,
                root,
                mapped_root,
            )

            self.mount_filesystems(
                boot,
                root,
                mapped_root,
            )

            self.copy_system()

            self.configure_fstab(
                boot,
                root,
                mapped_root,
            )
            self.progress.emit(48)

            self.configure_identity()
            self.progress.emit(51)

            self.configure_initramfs_encryption()
            self.progress.emit(53)

            self.prepare_network()
            self.progress.emit(56)

            self.configure_kernel()
            self.progress.emit(61)

            self.create_user()
            self.progress.emit(65)

            self.configure_root_account()
            self.progress.emit(67)

            self.configure_desktop()
            self.progress.emit(73)

            self.install_extra_packages()
            self.progress.emit(77)

            self.configure_profile()
            self.progress.emit(81)

            self.configure_mupdate()
            self.progress.emit(84)

            self.configure_swap()
            self.progress.emit(86)

            self.configure_bootloader()

            self.enable_services()
            self.progress.emit(93)

            self.generate_initramfs()

            self.finalize()
            self.progress.emit(99)

            self.cleanup_mounts()

            self.close_encryption()

            self.progress.emit(100)

            self.log(
                "=== Installation completed successfully ==="
            )

            self.finished_ok.emit()

        except Exception as exc:
            error_type = type(exc).__name__
            error_message = str(exc)

            self.log("")
            self.log("=" * 80)
            self.log("=== INSTALLATION FAILED ===")
            self.log(
                f"{error_type}: {error_message}"
            )
            self.log("Full Python traceback:")
            self.log(traceback.format_exc())
            self.log("=" * 80)

            try:
                self.log("Starting failure cleanup...")
                self.cleanup_mounts()
                self.log("Mount cleanup completed.")
            except Exception as cleanup_exc:
                self.log(
                    "Cleanup error: "
                    f"{type(cleanup_exc).__name__}: "
                    f"{cleanup_exc}"
                )

            try:
                self.close_encryption()
                self.log("Encryption cleanup completed.")
            except Exception as encryption_exc:
                self.log(
                    "Encryption cleanup error: "
                    f"{type(encryption_exc).__name__}: "
                    f"{encryption_exc}"
                )

            self.log("=== Installer stopped after failure ===")

            self.failed.emit(
                f"{error_type}: {error_message}"
            )

