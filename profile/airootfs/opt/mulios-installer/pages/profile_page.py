import json
import urllib.request

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QButtonGroup

from widgets.select_card import ProfileCard
from config.settings import PROFILE_DESCRIPTIONS, DEFAULT_PROFILE_SLUG

PROFILE_TREE_URL = "https://api.github.com/repos/MuliOS-dev/update/git/trees/main?recursive=1"


def _available_profiles():
    request = urllib.request.Request(PROFILE_TREE_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "MuliOS-Installer",
    })
    with urllib.request.urlopen(request, timeout=8) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("truncated") or not isinstance(data.get("tree"), list):
        raise ValueError("The MuliOS profile repository tree was incomplete.")

    slugs = set()
    for item in data["tree"]:
        path = item.get("path", "")
        if item.get("type") == "blob" and path.startswith("profiles/"):
            parts = path.split("/")
            if len(parts) == 3 and parts[2].endswith(".zip"):
                slugs.add(parts[1])

    return sorted(slug for slug in slugs if slug in PROFILE_DESCRIPTIONS)


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
        layout.addSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._slug_by_button = {}
        self._name_by_slug = {}
        self._available_slugs = [DEFAULT_PROFILE_SLUG]

        # Query the actual profile API directly. A separate Wi-Fi preflight can
        # incorrectly reject working internet connections; the API request is
        # the definitive test. On failure, keep Generic available and continue.
        try:
            discovered = _available_profiles()
            if DEFAULT_PROFILE_SLUG in discovered:
                self._available_slugs = discovered
            else:
                self.subtitle.setText(
                    "The profile repository did not list Generic. Generic remains selected."
                )
        except Exception as exc:
            self.subtitle.setText(
                "Could not load online profiles. Check internet access; "
                "Generic remains available. "
                f"Details: {type(exc).__name__}: {exc}"
            )

        default_button = None
        for i, slug in enumerate(self._available_slugs):
            name, description = PROFILE_DESCRIPTIONS[slug]
            card = ProfileCard("", name, description)
            row, col = divmod(i, 3)
            grid.addWidget(card, row, col)
            self.button_group.addButton(card)
            self._slug_by_button[card] = slug
            self._name_by_slug[slug] = name
            if slug == DEFAULT_PROFILE_SLUG:
                default_button = card

        layout.addLayout(grid)
        layout.addStretch()
        if default_button:
            default_button.setChecked(True)

    def selected_profile(self) -> str:
        checked = self.button_group.checkedButton()
        return self._slug_by_button.get(checked, DEFAULT_PROFILE_SLUG)

    def selected_profile_name(self) -> str:
        slug = self.selected_profile()
        return self._name_by_slug.get(slug, PROFILE_DESCRIPTIONS[DEFAULT_PROFILE_SLUG][0])

    def available_profiles(self):
        return list(self._available_slugs)
