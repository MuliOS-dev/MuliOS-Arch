"""
utils/validators.py

Small, dependency-free validation helpers shared across wizard pages.
Each returns (is_valid: bool, error_message: str).
"""

import re

HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]{0,62}$")
USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


def validate_hostname(value: str) -> tuple[bool, str]:
    value = value.strip()
    if not value:
        return False, "Computer name cannot be empty."
    if not HOSTNAME_RE.match(value):
        return False, "Use only letters, numbers, and hyphens (cannot start with a hyphen)."
    return True, ""


def validate_username(value: str) -> tuple[bool, str]:
    value = value.strip()
    if not value:
        return False, "Username cannot be empty."
    if not USERNAME_RE.match(value):
        return False, "Use lowercase letters, numbers, underscores, or hyphens; must start with a letter or underscore."
    return True, ""


def validate_password(password: str, confirm: str, min_length: int = 4) -> tuple[bool, str]:
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters."
    if password != confirm:
        return False, "Passwords do not match."
    return True, ""
