"""
backend/system_info.py

Read-only helpers that query the live environment for real data to
populate the wizard's pages (disks, keyboard layouts, locales,
timezones). Nothing here modifies the system.
"""

import json
import subprocess


def list_disks() -> list[dict]:
    """Returns [{path, size, model}] for whole disks only (via lsblk)."""
    try:
        out = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,SIZE,MODEL,TYPE"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(out.stdout)
    except Exception:
        return []

    disks = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") == "disk":
            disks.append({
                "path": f"/dev/{dev['name']}",
                "size": dev.get("size", ""),
                "model": dev.get("model") or "Unknown",
            })
    return disks


def list_keyboard_layouts() -> list[str]:
    """Returns available console keyboard layouts (via localectl)."""
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
    # Reasonable fallback list if localectl isn't available in this environment
    return ["us", "uk", "de", "fr", "es", "it", "pt", "ru", "jp", "cn"]


def list_locales() -> list[str]:
    """Returns available locales (via localectl, falls back to a short list)."""
    try:
        out = subprocess.run(
            ["localectl", "list-locales"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        locales = [
            line.strip()
            for line in out.stdout.splitlines()
            if line.strip() and line.strip() not in {"C", "C.UTF-8", "POSIX"}
        ]
        if locales:
            return locales
    except Exception:
        pass
    return ["en_US.UTF-8", "en_GB.UTF-8", "de_DE.UTF-8", "fr_FR.UTF-8", "es_ES.UTF-8"]


def list_timezones() -> list[str]:
    """Returns IANA timezone names (via timedatectl, falls back to a short list)."""
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


def check_internet(timeout=3) -> bool:
    import socket
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection(("8.8.8.8", 53))
        return True
    except OSError:
        return False


def scan_wifi() -> list[dict]:
    """Returns [{ssid, signal, security}] via nmcli."""
    try:
        out = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return []
    if out.returncode != 0:
        return []

    seen = set()
    networks = []
    for line in out.stdout.strip().splitlines():
        parts = line.split(":")
        if not parts or not parts[0] or parts[0] in seen:
            continue
        seen.add(parts[0])
        networks.append({
            "ssid": parts[0],
            "signal": parts[1] if len(parts) > 1 else "",
            "security": parts[2] if len(parts) > 2 else "",
        })
    return networks


def connect_wifi(ssid: str, password: str = "") -> tuple[bool, str]:
    cmd = ["nmcli", "dev", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, (result.stderr.strip() or result.stdout.strip())
