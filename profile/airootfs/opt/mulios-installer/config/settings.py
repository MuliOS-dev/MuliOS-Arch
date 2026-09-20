"""
config/settings.py

Central constants for the native MuliOS installer.
"""

import os

APP_NAME = "MuliOS Installer"
DISTRO_NAME = "MuliOS"
VERSION_STRING = "1.0.0"

INSTALLER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDING_DIR = os.path.join(INSTALLER_ROOT, "branding")
LOGO_PATH = os.path.join(BRANDING_DIR, "logo.png")

LOG_DIR = "/var/log/mulios"
INSTALL_LOG = os.path.join(LOG_DIR, "install.log")
SETUP_LOG = os.path.join(LOG_DIR, "setup.log")

INSTALL_MOUNTPOINT = "/mnt"

RELEASE_NOTES_URL = "https://github.com/MuliOS-dev"

PROFILES = [
    ("gaming", "Gaming",
     "Custom gaming kernel, performance tweaks, and gaming software.", ""),
    ("code", "Coding",
     "Compilers, Git, IDEs, SDKs, and container tools.", ""),
    ("ai", "AI Training",
     "AI frameworks, CUDA support, Python and ML libraries.", ""),
    ("school", "School",
     "Office suite, PDF tools, browsers, and educational apps.", ""),
    ("generic", "Casual",
     "A lightweight, balanced set of everyday applications.", ""),
    ("privacy", "Privacy",
     "Privacy-focused tools and hardened default settings.", ""),
]

DEFAULT_PROFILE_SLUG = "generic"

DESKTOP_ENVIRONMENTS = [
    ("Xfce4", "Xfce (lightweight, MuliOS default)"),
    ("Gnome", "GNOME"),
    ("Kde", "KDE Plasma"),
    ("Budgie", "Budgie"),
    ("Cinnamon", "Cinnamon"),
    (None, "None / minimal (server-style, no GUI)"),
]

BOOTLOADERS = [
    "Grub",
    "Systemd-boot",
    "Limine",
    "Efistub",
]

FILESYSTEMS = [
    "ext4",
    "btrfs",
    "xfs",
]
