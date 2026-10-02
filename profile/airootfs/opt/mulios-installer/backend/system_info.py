"""backend/system_info.py

Read-only helpers that query the live environment for real data to
populate the wizard's pages (disks, keyboard layouts, locales,
timezones and networking).
"""

import json
import subprocess


def list_disks() -> list[dict]:
    """Return whole disks with enough metadata for safe selection."""
    try:
        out = subprocess.run(
            [
                "lsblk", "-J",
                "-o", "NAME,SIZE,MODEL,TYPE,RM,TRAN,MOUNTPOINTS",
            ],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(out.stdout)
    except Exception:
        return []

    disks = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        mountpoints = [
            point for point in (dev.get("mountpoints") or []) if point
        ]
        disks.append({
            "path": f"/dev/{dev['name']}",
            "size": dev.get("size", ""),
            "model": dev.get("model") or "Unknown",
            "removable": bool(dev.get("rm", False)),
            "transport": dev.get("tran") or "",
            "mountpoints": mountpoints,
        })
    return disks


def list_keyboard_layouts() -> list[str]:
    try:
        out = subprocess.run(
            ["localectl", "list-keymaps"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        layouts = [line.strip() for line in out.stdout.splitlines() if line.strip()]
        if layouts:
            return layouts
    except Exception:
        pass
    return ["us", "uk", "de", "fr", "es", "it", "pt", "ru", "jp", "cn"]


def list_locales() -> list[str]:
    try:
        out = subprocess.run(
            ["localectl", "list-locales"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        locales = [
            line.strip() for line in out.stdout.splitlines()
            if line.strip() and line.strip() not in {"C", "C.UTF-8", "POSIX"}
        ]
        if locales:
            return locales
    except Exception:
        pass
    return ["en_US.UTF-8", "en_GB.UTF-8", "de_DE.UTF-8", "fr_FR.UTF-8", "es_ES.UTF-8"]


def list_timezones() -> list[str]:
    try:
        out = subprocess.run(
            ["timedatectl", "list-timezones"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        zones = [line.strip() for line in out.stdout.splitlines() if line.strip()]
        if zones:
            return zones
    except Exception:
        pass
    return ["UTC", "America/New_York", "America/Los_Angeles", "Europe/Paris", "Europe/London", "Asia/Tokyo"]


def _ensure_networkmanager() -> bool:
    """Make the live NetworkManager service available when possible."""
    try:
        state = subprocess.run(
            ["nmcli", "-t", "-f", "RUNNING", "general"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if state.returncode == 0 and state.stdout.strip().lower() == "running":
            subprocess.run(
                ["nmcli", "radio", "wifi", "on"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
            return True
    except (OSError, subprocess.TimeoutExpired):
        pass

    try:
        subprocess.run(
            ["systemctl", "start", "NetworkManager.service"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False

    try:
        state = subprocess.run(
            ["nmcli", "-t", "-f", "RUNNING", "general"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if state.returncode != 0 or state.stdout.strip().lower() != "running":
            return False
        subprocess.run(
            ["nmcli", "radio", "wifi", "on"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def check_internet(timeout=3) -> bool:
    """Return True when DNS or HTTPS Internet access works."""
    _ensure_networkmanager()
    commands = [
        ["getent", "hosts", "archlinux.org"],
        [
            "curl", "-4", "-fsS",
            "--connect-timeout", str(timeout),
            "--max-time", str(timeout + 1),
            "https://archlinux.org/",
        ],
    ]
    for command in commands:
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout + 2,
                check=False,
            )
            if result.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
    return False


def _split_nmcli_tsv(line: str) -> list[str]:
    """Split nmcli terse output while honoring escaped colons/backslashes."""
    fields = []
    current = []
    escaped = False

    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)

    if escaped:
        current.append("\\")
    fields.append("".join(current))
    return fields


def list_network_devices() -> list[dict]:
    """Return live network interfaces and their connection state."""
    if not _ensure_networkmanager():
        return []

    try:
        out = subprocess.run(
            ["nmcli", "-t", "--escape", "yes",
             "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    if out.returncode != 0:
        return []

    devices = []
    for line in out.stdout.splitlines():
        parts = _split_nmcli_tsv(line)
        if len(parts) >= 4:
            devices.append({
                "device": parts[0],
                "type": parts[1],
                "state": parts[2],
                "connection": parts[3],
            })
    return devices


def scan_wifi() -> list[dict]:
    """Return nearby Wi-Fi networks using NetworkManager."""
    if not _ensure_networkmanager():
        return []

    try:
        out = subprocess.run(
            ["nmcli", "-t", "--escape", "yes",
             "-f", "SSID,SIGNAL,SECURITY,CHAN,BARS",
             "device", "wifi", "list", "--rescan", "yes"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    if out.returncode != 0:
        return []

    networks = []
    seen = set()
    for line in out.stdout.splitlines():
        parts = _split_nmcli_tsv(line)
        if len(parts) < 5:
            continue
        ssid = parts[0]
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        try:
            signal = int(parts[1] or 0)
        except ValueError:
            signal = 0
        networks.append({
            "ssid": ssid,
            "signal": str(signal),
            "security": parts[2],
            "channel": parts[3],
            "bars": parts[4],
        })

    networks.sort(key=lambda item: int(item["signal"] or 0), reverse=True)
    return networks


def connect_wifi(ssid: str, password: str = "") -> tuple[bool, str]:
    if not _ensure_networkmanager():
        return False, "NetworkManager is not running in the live session."

    cmd = ["nmcli", "dev", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, (result.stderr.strip() or result.stdout.strip())
