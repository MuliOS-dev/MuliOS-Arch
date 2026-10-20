import json
import socket
import time
import urllib.error
import urllib.request

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QLabel,
    QButtonGroup, QPushButton,
)

from widgets.select_card import ProfileCard
from config.settings import PROFILE_DESCRIPTIONS, DEFAULT_PROFILE_SLUG

PROFILE_TREE_URL = "https://api.github.com/repos/MuliOS-dev/mupdate/git/trees/main?recursive=1"
REQUEST_TIMEOUT = 5
REQUEST_ATTEMPTS = 3


def _profile_slug_from_path(path: str):
    """Resolve a supported profile ZIP path from the MUpdate repository."""
    if not path.startswith("profiles/") or not path.endswith(".zip"):
        return None

    parts = path.split("/")
    if len(parts) == 2:
        filename = parts[1]
        if not filename.startswith("latest-"):
            return None
        slug = filename[len("latest-"):-len(".zip")]
        if slug == "game":
            slug = "gaming"
        return slug

    if len(parts) == 3:
        return parts[1]

    return None


def _available_profiles():
    """Fetch profile metadata with bounded retries and actionable errors."""
    request = urllib.request.Request(
        PROFILE_TREE_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MuliOS-Installer",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    last_error = None

    for attempt in range(REQUEST_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                data = json.loads(response.read().decode("utf-8"))

            if data.get("truncated") or not isinstance(data.get("tree"), list):
                raise ValueError("GitHub returned an incomplete profile listing.")

            slugs = set()
            for item in data["tree"]:
                if item.get("type") != "blob":
                    continue
                slug = _profile_slug_from_path(item.get("path", ""))
                if slug in PROFILE_DESCRIPTIONS:
                    slugs.add(slug)

            if DEFAULT_PROFILE_SLUG not in slugs:
                raise ValueError("The online profile repository does not contain Generic.")

            return sorted(slugs)
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError,
                ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 < REQUEST_ATTEMPTS:
                time.sleep(0.35 * (attempt + 1))

    reason = getattr(last_error, "reason", last_error)
    if isinstance(reason, socket.gaierror):
        detail = "DNS lookup failed. Ethernet may be connected, but name resolution is not working."
    elif isinstance(last_error, (TimeoutError, socket.timeout)):
        detail = "The request timed out. Check the connection, DNS, or firewall."
    elif isinstance(last_error, urllib.error.HTTPError):
        detail = f"GitHub returned HTTP {last_error.code}."
    else:
        detail = f"{type(last_error).__name__}: {reason}"
    raise RuntimeError(detail) from last_error


class ProfilePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("How will you primarily use this computer?")
        title.setObjectName("TitleLabel")
        title.setWordWrap(True)
        layout.addWidget(title)

        self.subtitle = QLabel(
            "Generic is selected by default. Specialized profiles are downloaded "
            "and installed by MUpdate from the official profile repository."
        )
        self.subtitle.setObjectName("SubtitleLabel")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        status_row = QHBoxLayout()
        status_row.addStretch()
        self.refresh_button = QPushButton("Refresh profiles")
        self.refresh_button.setObjectName("SecondaryButton")
        self.refresh_button.clicked.connect(self.refresh_profiles)
        status_row.addWidget(self.refresh_button)
        layout.addLayout(status_row)

        self.grid = QGridLayout()
        self.grid.setSpacing(14)
        layout.addLayout(self.grid)
        layout.addStretch()

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._slug_by_button = {}
        self._name_by_slug = {}
        self._available_slugs = [DEFAULT_PROFILE_SLUG]
        self._render_profiles(self._available_slugs)
        self.refresh_profiles(initial=True)

    def _render_profiles(self, slugs):
        previous = self.selected_profile() if self._slug_by_button else DEFAULT_PROFILE_SLUG

        for button in self.button_group.buttons():
            self.button_group.removeButton(button)
            self.grid.removeWidget(button)
            button.deleteLater()

        self._slug_by_button = {}
        self._name_by_slug = {}
        self._available_slugs = list(slugs) or [DEFAULT_PROFILE_SLUG]
        if DEFAULT_PROFILE_SLUG not in self._available_slugs:
            self._available_slugs.insert(0, DEFAULT_PROFILE_SLUG)

        for i, slug in enumerate(self._available_slugs):
            name, description = PROFILE_DESCRIPTIONS[slug]
            card = ProfileCard("", name, description)
            row, col = divmod(i, 3)
            self.grid.addWidget(card, row, col)
            self.button_group.addButton(card)
            self._slug_by_button[card] = slug
            self._name_by_slug[slug] = name

        selected = previous if previous in self._slug_by_button else DEFAULT_PROFILE_SLUG
        for button, slug in self._slug_by_button.items():
            button.setChecked(slug == selected)

    def refresh_profiles(self, initial=False):
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Checking..." if initial else "Refreshing...")
        self.subtitle.setText(
            "Checking the MUpdate profile repository…"
            if initial else "Retrying the profile repository connection…"
        )

        try:
            discovered = _available_profiles()
        except Exception as exc:
            # Keep any profiles already loaded; on first launch Generic remains
            # selectable and users can retry without restarting the installer.
            if initial or len(self._available_slugs) <= 1:
                self._render_profiles([DEFAULT_PROFILE_SLUG])
            self.subtitle.setText(
                "Could not load online profiles. Generic remains available. "
                f"{exc} Use Refresh profiles to try again."
            )
        else:
            self._render_profiles(discovered)
            self.subtitle.setText(
                f"Loaded {len(discovered)} profiles from the official repository."
            )
        finally:
            self.refresh_button.setEnabled(True)
            self.refresh_button.setText("Refresh profiles")

    def selected_profile(self) -> str:
        checked = self.button_group.checkedButton()
        return self._slug_by_button.get(checked, DEFAULT_PROFILE_SLUG)

    def selected_profile_name(self) -> str:
        slug = self.selected_profile()
        return self._name_by_slug.get(
            slug, PROFILE_DESCRIPTIONS[DEFAULT_PROFILE_SLUG][0]
        )

    def available_profiles(self):
        return list(self._available_slugs)
