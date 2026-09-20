from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
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
        self.selected_disk = None
        self.boot_partition = None
        self.root_partition = None
        self.root_device = None
        self.kernel_package = "linux"

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log(self, message: str):
        message = str(message)

        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

            with LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(message + "\n")
        except Exception:
            pass

        self.log_line.emit(message)

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
    ):
        command = [str(x) for x in command]

        self.log(
            "$ " +
            " ".join(
                shlex.quote(x)
                for x in command
            )
        )

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

        if input_text is not None and process.stdin is not None:
            try:
                process.stdin.write(input_text)
                process.stdin.close()
            except Exception:
                try:
                    process.stdin.close()
                except Exception:
                    pass

        output = []

        if process.stdout is not None:
            for line in process.stdout:
                line = line.rstrip()
                output.append(line)
                self.log(line)

        process.wait()

        result = "\n".join(output)

        if check and process.returncode != 0:
            raise InstallError(
                "Command failed with exit code "
                f"{process.returncode}: "
                + " ".join(command)
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

        self.progress.emit(5)

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
            "size=1G, type=uefi\n"
            "type=linux\n"
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

        self.progress.emit(10)

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

        self.log(
            "Formatting EFI system partition..."
        )

        self.run_command(
            [
                "mkfs.fat",
                "-F",
                "32",
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
                    filesystem_root,
                ]
            )

        elif filesystem == "btrfs":
            self.run_command(
                [
                    "mkfs.btrfs",
                    "-f",
                    filesystem_root,
                ]
            )

        elif filesystem == "xfs":
            self.run_command(
                [
                    "mkfs.xfs",
                    "-f",
                    filesystem_root,
                ]
            )

        else:
            raise InstallError(
                f"Unsupported filesystem: {filesystem}"
            )

        self.progress.emit(15)

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

        self.mounts_active = True

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
                "--info=progress2",
                *excluded,
                f"{source}/",
                f"{self.target}/",
            ]
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

        self.progress.emit(35)

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

        if not hostname:
            hostname = "mulios"

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

        self.write_file(
            self.target / "etc/locale.conf",
            f"LANG={locale}\n",
        )

        self.write_file(
            self.target / "etc/vconsole.conf",
            f"KEYMAP={keyboard}\n",
        )

        locale_gen = (
            self.target /
            "etc/locale.gen"
        )

        if locale_gen.exists():
            text = locale_gen.read_text(
                encoding="utf-8",
                errors="replace",
            )

            output = []

            for line in text.splitlines():
                stripped = line.lstrip(
                    "#"
                ).strip()

                if stripped.startswith(
                    locale + " "
                ):
                    output.append(
                        stripped
                    )
                else:
                    output.append(
                        line
                    )

            locale_gen.write_text(
                "\n".join(output) + "\n",
                encoding="utf-8",
            )

        zoneinfo = (
            self.target /
            "usr/share/zoneinfo" /
            timezone
        )

        localtime = (
            self.target /
            "etc/localtime"
        )

        if localtime.exists() or localtime.is_symlink():
            localtime.unlink()

        if zoneinfo.exists():
            localtime.symlink_to(
                Path(
                    "/usr/share/zoneinfo"
                ) / timezone
            )

        self.chroot(
            ["locale-gen"]
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

        if not mirrorlist.exists():
            self.log(
                "Mirrorlist not found; leaving "
                "the existing pacman configuration unchanged."
            )
            return

        if not mirror_region:
            mirror_region = "Worldwide"

        if mirror_region == "Worldwide":
            self.ensure_active_mirror(
                mirrorlist
            )
            return

        text = mirrorlist.read_text(
            encoding="utf-8",
            errors="replace",
        )

        lines = text.splitlines()

        region_aliases = {
            "United States": [
                "United States",
            ],
            "Germany": [
                "Germany",
            ],
            "France": [
                "France",
            ],
            "United Kingdom": [
                "United Kingdom",
                "Great Britain",
            ],
            "Canada": [
                "Canada",
            ],
            "Australia": [
                "Australia",
            ],
            "Japan": [
                "Japan",
            ],
            "Brazil": [
                "Brazil",
            ],
            "India": [
                "India",
            ],
        }

        wanted = region_aliases.get(
            mirror_region,
            [mirror_region],
        )

        current = ""

        output = []

        for line in lines:
            heading = re.match(
                r"^##(?:\s+Score:.*?,)?\s*(.+?)\s*$",
                line,
            )

            if heading:
                current = heading.group(1).strip()

            if re.match(
                r"^#?\s*Server\s*=",
                line,
            ):
                enabled = any(
                    alias.lower()
                    in current.lower()
                    for alias in wanted
                )

                stripped = line.lstrip()

                if enabled:
                    line = re.sub(
                        r"^#\s*",
                        "",
                        line,
                    )
                else:
                    if not stripped.startswith(
                        "#"
                    ):
                        line = "#" + line

            output.append(line)

        new_text = (
            "\n".join(output) +
            "\n"
        )

        mirrorlist.write_text(
            new_text,
            encoding="utf-8",
        )

        self.ensure_active_mirror(
            mirrorlist
        )

        self.log(
            f"Mirror region configured: "
            f"{mirror_region}"
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
            r"(?m)^Server\s*=",
            text,
        ):
            return

        lines = text.splitlines()

        for index, line in enumerate(
            lines
        ):
            if re.match(
                r"^#\s*Server\s*=",
                line,
            ):
                lines[index] = re.sub(
                    r"^#\s*",
                    "",
                    line,
                )
                mirrorlist.write_text(
                    "\n".join(lines) + "\n",
                    encoding="utf-8",
                )
                return

        raise InstallError(
            "No usable Arch Linux mirror "
            "was found in the target mirrorlist."
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

        resolv = (
            self.target /
            "etc/resolv.conf"
        )

        if resolv.exists() or resolv.is_symlink():
            resolv.unlink()

        live_resolv = Path(
            "/etc/resolv.conf"
        )

        if live_resolv.exists():
            try:
                shutil.copy2(
                    live_resolv,
                    resolv,
                )
            except Exception as exc:
                self.log(
                    f"Could not copy resolv.conf: {exc}"
                )

        self.configure_multilib()

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

        if not self.pacman_synced:
            self.log(
                "Preparing target pacman keyring..."
            )

            self.chroot(
                [
                    "mkdir",
                    "-p",
                    "/etc/pacman.d/gnupg",
                ]
            )

            self.chroot(
                [
                    "chmod",
                    "700",
                    "/etc/pacman.d/gnupg",
                ]
            )

            self.chroot(
                [
                    "chown",
                    "-R",
                    "root:root",
                    "/etc/pacman.d/gnupg",
                ]
            )

            keyring_check = self.chroot(
                [
                    "pacman-key",
                    "--list-keys",
                ],
                check=False,
            )

            if not keyring_check.strip():
                self.log(
                    "Initializing target pacman keyring..."
                )

                self.chroot(
                    [
                        "rm",
                        "-rf",
                        "/etc/pacman.d/gnupg",
                    ]
                )

                self.chroot(
                    [
                        "mkdir",
                        "-p",
                        "/etc/pacman.d/gnupg",
                    ]
                )

                self.chroot(
                    [
                        "chmod",
                        "700",
                        "/etc/pacman.d/gnupg",
                    ]
                )

                self.chroot(
                    [
                        "chown",
                        "root:root",
                        "/etc/pacman.d/gnupg",
                    ]
                )

                self.chroot(
                    [
                        "pacman-key",
                        "--init",
                    ]
                )

                self.chroot(
                    [
                        "pacman-key",
                        "--populate",
                        "archlinux",
                    ]
                )

            self.chroot(
                [
                    "pacman-key",
                    "--list-keys",
                ]
            )

            self.log(
                "Synchronizing target package databases..."
            )

            self.chroot(
                [
                    "pacman",
                    "-Syu",
                    "--noconfirm",
                ]
            )

            self.pacman_synced = True

        self.log(
            "Installing packages: " +
            " ".join(packages)
        )

        self.chroot(
            [
                "pacman",
                "-S",
                "--needed",
                "--noconfirm",
                *packages,
            ]
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

        if not password:
            raise InstallError(
                "User password cannot be empty."
            )

        self.log(
            f"Creating user account: {username}"
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

        self.chroot(
            ["chpasswd"],
            input_text=(
                f"{username}:{password}\n"
            ),
        )

        sudoers = (
            self.target /
            "etc/sudoers.d/mulios-wheel"
        )

        self.write_file(
            sudoers,
            "%wheel ALL=(ALL:ALL) ALL\n",
            mode=0o440,
        )

        self.progress.emit(60)

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
        kernel = str(
            self.state.get(
                "kernel",
                "linux",
            )
        ).strip().lower()

        allowed = {
            "linux": "linux",
            "linux-lts": "linux-lts",
            "linux-zen": "linux-zen",
            "linux-hardened": "linux-hardened",
        }

        package = allowed.get(
            kernel
        )

        if package is None:
            raise InstallError(
                f"Unsupported kernel selection: {kernel}"
            )

        self.kernel_package = package

        self.log(
            f"Installing selected kernel: {package}"
        )

        packages = [
            package,
            "linux-firmware",
        ]

        if self.encryption_enabled():
            packages.append(
                "cryptsetup"
            )

        self.pacman_install(
            packages
        )

    def kernel_paths(self):
        mapping = {
            "linux": (
                "vmlinuz-linux",
                "initramfs-linux.img",
            ),
            "linux-lts": (
                "vmlinuz-linux-lts",
                "initramfs-linux-lts.img",
            ),
            "linux-zen": (
                "vmlinuz-linux-zen",
                "initramfs-linux-zen.img",
            ),
            "linux-hardened": (
                "vmlinuz-linux-hardened",
                "initramfs-linux-hardened.img",
            ),
        }

        return mapping[
            self.kernel_package
        ]

    # ------------------------------------------------------------------
    # Desktop
    # ------------------------------------------------------------------

    def configure_desktop(self):
        desktop = str(
            self.state.get(
                "desktop_environment",
                "Kde",
            )
        ).strip().lower()

        if desktop == "kde":
            packages = [
                "plasma-desktop",
                "sddm",
                "dolphin",
            ]

            service = "sddm"

        elif desktop in {
            "xfce",
            "xfce4",
        }:
            packages = [
                "xfce4",
                "xfce4-goodies",
                "lightdm",
                "lightdm-gtk-greeter",
            ]

            service = "lightdm"

        elif desktop == "gnome":
            packages = [
                "gnome",
                "gdm",
            ]

            service = "gdm"

        elif desktop == "cinnamon":
            packages = [
                "cinnamon",
                "lightdm",
                "lightdm-gtk-greeter",
            ]

            service = "lightdm"

        elif desktop == "budgie":
            packages = [
                "budgie-desktop",
                "lightdm",
                "lightdm-gtk-greeter",
            ]

            service = "lightdm"

        elif desktop in {
            "",
            "none",
            "none / minimal",
        }:
            self.log(
                "No desktop environment selected."
            )
            return

        else:
            raise InstallError(
                "Unsupported desktop environment: "
                f"{desktop}"
            )

        self.pacman_install(
            packages
        )

        self.chroot(
            [
                "systemctl",
                "enable",
                service,
            ]
        )

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

        hooks = match.group(1).split()

        if "systemd" in hooks:
            required = [
                "base",
                "systemd",
                "keyboard",
                "autodetect",
                "microcode",
                "modconf",
                "kms",
                "sd-vconsole",
                "block",
                "sd-encrypt",
                "filesystems",
                "fsck",
            ]
        else:
            required = [
                "base",
                "udev",
                "keyboard",
                "keymap",
                "autodetect",
                "microcode",
                "modconf",
                "kms",
                "consolefont",
                "block",
                "encrypt",
                "filesystems",
                "fsck",
            ]

        final_hooks = []

        for hook in required:
            if hook not in final_hooks:
                final_hooks.append(
                    hook
                )

        replacement = (
            "HOOKS=(" +
            " ".join(final_hooks) +
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
            "Configured encrypted-root "
            "mkinitcpio hooks."
        )

    # ------------------------------------------------------------------
    # Kernel command line
    # ------------------------------------------------------------------

    def kernel_cmdline(self):
        root_uuid = self.block_uuid(
            self.mapped_root or
            self.root_partition
        )

        args = [
            f"root=UUID={root_uuid}",
            "rw",
        ]

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
    # Bootloaders
    # ------------------------------------------------------------------

    def configure_grub(self):
        self.log(
            "Installing GRUB..."
        )

        self.pacman_install(
            [
                "grub",
                "efibootmgr",
            ]
        )

        self.chroot(
            [
                "grub-install",
                "--target=x86_64-efi",
                "--efi-directory=/boot",
                "--bootloader-id=MuliOS",
                "--recheck",
            ]
        )

        cmdline = self.kernel_cmdline()

        grub_default = (
            self.target /
            "etc/default/grub"
        )

        if grub_default.exists():
            text = grub_default.read_text(
                encoding="utf-8",
                errors="replace",
            )

            line = (
                f'GRUB_CMDLINE_LINUX_DEFAULT='
                f'"{cmdline}"'
            )

            text = re.sub(
                r'(?m)^#?\s*'
                r'GRUB_CMDLINE_LINUX_DEFAULT=.*$',
                line,
                text,
            )

            grub_default.write_text(
                text,
                encoding="utf-8",
            )

        self.chroot(
            [
                "grub-mkconfig",
                "-o",
                "/boot/grub/grub.cfg",
            ]
        )

    def configure_systemd_boot(self):
        self.log(
            "Installing systemd-boot..."
        )

        self.pacman_install(
            ["systemd"]
        )

        self.chroot(
            [
                "bootctl",
                "--path=/boot",
                "install",
            ]
        )

        kernel_name, initramfs_name = (
            self.kernel_paths()
        )

        kernel = (
            self.target /
            "boot" /
            kernel_name
        )

        initramfs = (
            self.target /
            "boot" /
            initramfs_name
        )

        if not kernel.exists():
            raise InstallError(
                f"Kernel image not found: {kernel_name}"
            )

        if not initramfs.exists():
            raise InstallError(
                f"Initramfs not found: {initramfs_name}"
            )

        loader_dir = (
            self.target /
            "boot/loader"
        )

        entries_dir = (
            loader_dir /
            "entries"
        )

        entries_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.write_file(
            loader_dir /
            "loader.conf",
            "default mulios.conf\n"
            "timeout 5\n",
        )

        cmdline = self.kernel_cmdline()

        entry = (
            "title MuliOS\n"
            f"linux /{kernel_name}\n"
            f"initrd /{initramfs_name}\n"
            f"options {cmdline}\n"
        )

        self.write_file(
            entries_dir /
            "mulios.conf",
            entry,
        )

    def find_limine_binary(self):
        candidates = [
            self.target /
            "usr/share/limine/BOOTX64.EFI",
            self.target /
            "usr/lib/limine/BOOTX64.EFI",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        result = self.chroot(
            [
                "bash",
                "-c",
                "find /usr/share /usr/lib "
                "-type f \\( "
                "-iname 'BOOTX64.EFI' -o "
                "-iname 'limine*.efi' "
                "\\) 2>/dev/null",
            ],
            check=False,
        )

        for line in result.splitlines():
            line = line.strip()

            if not line:
                continue

            candidate = (
                self.target /
                line.lstrip("/")
            )

            if candidate.exists():
                return candidate

        return None

    def configure_limine(self):
        self.log(
            "Installing Limine..."
        )

        self.pacman_install(
            ["limine"]
        )

        limine_binary = (
            self.find_limine_binary()
        )

        if limine_binary is None:
            raise InstallError(
                "Limine EFI executable was not found."
            )

        efi_dir = (
            self.target /
            "boot/EFI/BOOT"
        )

        efi_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            limine_binary,
            efi_dir /
            "BOOTX64.EFI",
        )

        kernel_name, initramfs_name = (
            self.kernel_paths()
        )

        cmdline = self.kernel_cmdline()

        config = (
            "timeout: 5\n"
            "interface_branding: MuliOS\n"
            "\n"
            "/MuliOS\n"
            "    protocol: linux\n"
            f"    kernel_path: "
            f"boot():/{kernel_name}\n"
            f"    kernel_cmdline: {cmdline}\n"
            f"    module_path: "
            f"boot():/{initramfs_name}\n"
        )

        self.write_file(
            self.target /
            "boot/limine.conf",
            config,
        )

    def configure_efistub(self):
        self.log(
            "Configuring EFI stub..."
        )

        self.pacman_install(
            ["efibootmgr"]
        )

        kernel_name, initramfs_name = (
            self.kernel_paths()
        )

        kernel = (
            self.target /
            "boot" /
            kernel_name
        )

        if not kernel.exists():
            raise InstallError(
                f"Kernel image not found: {kernel_name}"
            )

        cmdline = (
            self.kernel_cmdline() +
            f" initrd=\\{initramfs_name}"
        )

        self.chroot(
            [
                "efibootmgr",
                "-c",
                "-d",
                self.selected_disk,
                "-p",
                "1",
                "-L",
                "MuliOS",
                "-l",
                "\\" + kernel_name,
                "-u",
                cmdline,
            ]
        )

    def configure_bootloader(self):
        bootloader = str(
            self.state.get(
                "bootloader",
                "Grub",
            )
        ).strip().lower()

        self.log(
            f"Selected bootloader: {bootloader}"
        )

        if bootloader == "grub":
            self.configure_grub()

        elif bootloader in {
            "systemd-boot",
            "systemd boot",
        }:
            self.configure_systemd_boot()

        elif bootloader == "limine":
            self.configure_limine()

        elif bootloader in {
            "efistub",
            "efi stub",
        }:
            self.configure_efistub()

        else:
            raise InstallError(
                f"Unsupported bootloader: {bootloader}"
            )

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

        self.progress.emit(95)

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

        self.log(
            "Cleaning up installation mounts..."
        )

        for path in (
            self.target / "run",
            self.target / "sys",
            self.target / "proc",
            self.target / "dev",
        ):
            self.run_command(
                [
                    "umount",
                    "-R",
                    str(path),
                ],
                check=False,
            )

        self.run_command(
            [
                "umount",
                str(
                    self.target / "boot"
                ),
            ],
            check=False,
        )

        self.run_command(
            [
                "umount",
                str(self.target),
            ],
            check=False,
        )

        self.mounts_active = False

    # ------------------------------------------------------------------
    # Main installation sequence
    # ------------------------------------------------------------------

    def run(self):
        try:
            self.require_root()

            self.log(
                "=== MuliOS Native Installer ==="
            )

            self.log(
                "Starting installation."
            )

            if not self.is_uefi():
                raise InstallError(
                    "MuliOS currently requires "
                    "a UEFI boot environment."
                )

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

            self.configure_identity()

            self.configure_initramfs_encryption()

            self.prepare_network()

            self.configure_kernel()

            self.create_user()

            self.configure_root_account()

            self.configure_desktop()

            self.install_extra_packages()

            self.configure_profile()

            self.configure_mupdate()

            self.configure_swap()

            self.configure_bootloader()

            self.enable_services()

            self.generate_initramfs()

            self.finalize()

            self.cleanup_mounts()

            self.close_encryption()

            self.progress.emit(100)

            self.log(
                "=== Installation completed successfully ==="
            )

            self.finished_ok.emit()

        except Exception as exc:
            self.log(
                f"ERROR: {exc}"
            )

            self.log(
                "=== Installation failed ==="
            )

            try:
                self.cleanup_mounts()
            except Exception:
                pass

            try:
                self.close_encryption()
            except Exception:
                pass

            self.failed.emit(
                str(exc)
            )

