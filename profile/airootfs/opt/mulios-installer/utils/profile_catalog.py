"""Discover non-empty profiles from the official MuliOS profile repository."""

from __future__ import annotations

import json
import subprocess
import urllib.request


PROFILE_REPOSITORY = "https://api.github.com/repos/MuliOS-dev/update/git/trees/main?recursive=1"

# Descriptions are intentionally local and stable: the remote repository is
# only used to discover which profile folders currently contain files.
PROFILE_DESCRIPTIONS = {
    "generic": (
        "Generic",
        "Balanced default configuration for everyday use. Recommended when "
        "you do not need a specialized profile.",
    ),
    "game": (
        "Gaming",
        "Gaming-oriented configuration intended for responsive gameplay and "
        "gaming workloads.",
    ),
    "gaming": (
        "Gaming",
        "Gaming-oriented configuration intended for responsive gameplay and "
        "gaming workloads.",
    ),
    "code": (
        "Code",
        "Development-oriented configuration for programming, software "
        "engineering, and development tools.",
    ),
    "ai": (
        "AI",
        "Configuration intended for AI development and machine-learning "
        "workloads.",
    ),
    "study": (
        "Study",
        "General configuration for studying, learning, and schoolwork.",
    ),
    "privacy": (
        "Privacy",
        "Privacy-oriented configuration with additional privacy-focused "
        "settings.",
    ),
    "server": (
        "Server",
        "Configuration intended for server workloads and services.",
    ),
}


def has_connected_wifi() -> bool:
    """Return true only when NetworkManager reports an active Wi-Fi link."""
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "TYPE,STATE", "device"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False

    if result.returncode != 0:
        return False

    for line in result.stdout.splitlines():
        parts = line.strip().split(":", 1)
        if len(parts) == 2 and parts[0] == "wifi" and parts[1] == "connected":
            return True
    return False


def discover_profiles(timeout: float = 3.0) -> list[tuple[str, str, str, str]]:
    """Return known profile folders that contain at least one file.

    On lookup failure, expose only the built-in generic default. A profile is
    considered available when the official tree has any file below its folder.
    """
    generic = [
        (
            "generic",
            PROFILE_DESCRIPTIONS["generic"][0],
            PROFILE_DESCRIPTIONS["generic"][1],
            "",
        )
    ]

    try:
        request = urllib.request.Request(
            PROFILE_REPOSITORY,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "MuliOS-Installer",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            tree = json.load(response).get("tree", [])
    except (OSError, ValueError, TimeoutError):
        return generic

    nonempty = set()
    for entry in tree:
        path = str(entry.get("path", ""))
        if not path.startswith("profiles/") or entry.get("type") != "blob":
            continue
        remainder = path[len("profiles/"):]
        slug = remainder.split("/", 1)[0].strip().lower()
        if slug:
            nonempty.add(slug)

    found = []
    seen = set()
    # Use the repository's actual folder names as MUpdate arguments.
    for slug in sorted(nonempty):
        if slug in seen or slug not in PROFILE_DESCRIPTIONS:
            continue
        seen.add(slug)
        name, description = PROFILE_DESCRIPTIONS[slug]
        found.append((slug, name, description, ""))

    if "generic" not in seen:
        found.insert(0, generic[0])
    else:
        found.sort(key=lambda item: (item[0] != "generic", item[1].lower()))

    return found or generic
