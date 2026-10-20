import json
import urllib.request

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QButtonGroup

from widgets.select_card import ProfileCard
from config.settings import PROFILE_DESCRIPTIONS, DEFAULT_PROFILE_SLUG

PROFILE_TREE_URL = "https://api.github.com/repos/MuliOS-dev/update/git/trees/main?recursive=1"


def _profile_slug_from_path(path: str):
    """Resolve a supported profile ZIP path from the update repository."""
    if not path.startswith("profiles/") or not path.endswith(".zip"):
        return None

    parts = path.split("/")

    # Current repository layout: profiles/latest-ai.zip, profiles/latest-game.zip, etc.
    if len(parts) == 2:
        filename = parts[1]
        if not filename.startswith("latest-"):
            return None
        slug = filename[len("latest-"):-len(".zip")]
        if slug == "game":
            slug = "gaming"
        return slug

    # Also accept profile ZIPs nested under profiles/<slug>/ for compatibility.
    if len(parts) == 3:
        return parts[1]

    return None


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
        if item.get("type") != "blob":
            continue
        slug = _profile_slug_from_path(item.get("path", ""))
        if slug in PROFILE_DESCRIPTIONS:
            slugs.add(slug)

    return sorted(slugs)


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

        # Query the profile repository directly. Do not rely on a separate
        # network-page check; the live API request is the definitive test.
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
