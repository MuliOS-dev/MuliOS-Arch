import re

from pathlib import Path


def validate_hostname(hostname: str) -> tuple[bool, str]:
    hostname = hostname.strip()

    if not hostname:
        return False, "Computer name cannot be empty."

    if len(hostname) > 63:
        return False, "Computer name cannot be longer than 63 characters."

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", hostname):
        return False, "Computer name contains invalid characters."

    return True, ""


def validate_username(username: str) -> tuple[bool, str]:
    username = username.strip()

    if not username:
        return False, "Username cannot be empty."

    if len(username) > 32:
        return False, "Username cannot be longer than 32 characters."

    if not re.fullmatch(r"[a-z_][a-z0-9_-]*[$]?", username):
        return False, (
            "Username must use lowercase letters, numbers, "
            "underscores, and hyphens."
        )

    return True, ""


def validate_password(
    password: str,
    confirm: str,
    min_length: int = 8,
) -> tuple[bool, str]:
    if password != confirm:
        return False, "Passwords do not match."

    if not password:
        return True, (
            "Warning: no password was entered. "
            "The installed user will have an empty password."
        )

    if len(password) < min_length:
        return True, (
            f"Warning: this password is weak because it is shorter "
            f"than {min_length} characters."
        )

    return True, ""
