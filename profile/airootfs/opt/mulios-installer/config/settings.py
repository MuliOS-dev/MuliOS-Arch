"""
Central constants for the native MuliOS installer.
"""

import os

APP_NAME = "MuliOS Installer"
DISTRO_NAME = "MuliOS"
VERSION_STRING = "1.0.2"

INSTALLER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDING_DIR = os.path.join(INSTALLER_ROOT, "branding")
LOGO_PATH = os.path.join(BRANDING_DIR, "logo.png")

LOG_DIR = "/var/log/mulios"
INSTALL_LOG = os.path.join(LOG_DIR, "install.log")
SETUP_LOG = os.path.join(LOG_DIR, "setup.log")

INSTALL_MOUNTPOINT = "/mnt"
RELEASE_NOTES_URL = "https://github.com/MuliOS-dev"

# The installer discovers which of these profiles actually contain a ZIP
# directly inside profiles/<slug>/ in MuliOS-dev/update. These descriptions
# are deliberately local and do not depend on repository metadata.
PROFILE_DESCRIPTIONS = {
    "ai": ("AI", "For AI development and machine-learning workloads."),
    "code": ("Code", "For programming, software development, and build tools."),
    "gaming": ("Gaming", "For gaming workloads and gaming-focused kernel packages."),
    "generic": ("Generic", "A balanced default configuration for everyday use."),
    "privacy": ("Privacy", "For users who prioritize privacy-focused configuration."),
    "server": ("Server", "For server workloads and service-oriented systems."),
    "study": ("Study", "For studying, learning, and everyday schoolwork."),
}

PROFILES = [
    (slug, name, description, "")
    for slug, (name, description) in PROFILE_DESCRIPTIONS.items()
]

DEFAULT_PROFILE_SLUG = "generic"

# MuliOS uses KDE Plasma for installed systems.
DESKTOP_ENVIRONMENTS = [
    ("kde", "KDE Plasma"),
]

# MuliOS installations use GRUB.
BOOTLOADERS = [
    "grub",
]

FILESYSTEMS = [
    "ext4",
    "btrfs",
    "xfs",
]
