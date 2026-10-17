from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QButtonGroup
)

from widgets.select_card import ProfileCard
from config.settings import DEFAULT_PROFILE_SLUG
from utils.profile_catalog import discover_profiles


class ProfilePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(12)

        title = QLabel("How will you primarily use this computer?")
        title.setObjectName("TitleLabel")
        title.setWordWrap(True)
        self.layout.addWidget(title)

        self.subtitle = QLabel(
            "Choose an optional profile from the official MuliOS profile "
            "repository. MUpdate manages profile packages; Generic remains "
            "the default if Wi-Fi is unavailable."
        )
        self.subtitle.setObjectName("SubtitleLabel")
        self.subtitle.setWordWrap(True)
        self.layout.addWidget(self.subtitle)

        self.grid = QGridLayout()
        self.grid.setSpacing(14)
        self.layout.addLayout(self.grid)
        self.layout.addStretch()

        self.button_group = None
        self._slug_by_button = {}
        self._profiles = []
        self.refresh_availability(wifi_available=False, force=True)

    def refresh_availability(self, wifi_available: bool, force: bool = False):
        """Refresh choices when the wizard reaches this page."""
        profiles = discover_profiles() if wifi_available else [
            (
                "generic",
                "Generic",
                "Balanced default configuration for everyday use. "
                "Recommended when you do not need a specialized profile.",
                "",
            )
        ]

        if not force and profiles == self._profiles:
            return

        previous = self.selected_profile() if self.button_group else DEFAULT_PROFILE_SLUG
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._slug_by_button = {}
        self._profiles = profiles

        for i, (slug, name, description, icon) in enumerate(profiles):
            card = ProfileCard(icon, name, description)
            row, col = divmod(i, 3)
            self.grid.addWidget(card, row, col)
            self.button_group.addButton(card)
            self._slug_by_button[card] = slug

        selected = next(
            (button for button, slug in self._slug_by_button.items() if slug == previous),
            None,
        )
        if selected is None:
            selected = next(
                (button for button, slug in self._slug_by_button.items()
                 if slug == DEFAULT_PROFILE_SLUG),
                next(iter(self._slug_by_button), None),
            )
        if selected is not None:
            selected.setChecked(True)

        if wifi_available:
            self.subtitle.setText(
                "Choose an optional profile discovered in the official MuliOS "
                "profile repository. MUpdate manages profile packages; Generic "
                "is the balanced default."
            )
        else:
            self.subtitle.setText(
                "Wi-Fi is not connected. Profile selection is skipped and "
                "Generic will be kept as the default."
            )

    def selected_profile(self) -> str:
        if self.button_group is None:
            return DEFAULT_PROFILE_SLUG
        checked = self.button_group.checkedButton()
        if checked is None:
            return DEFAULT_PROFILE_SLUG
        return self._slug_by_button.get(checked, DEFAULT_PROFILE_SLUG)

    def selected_profile_name(self) -> str:
        slug = self.selected_profile()
        for profile_slug, name, _, _ in self._profiles:
            if profile_slug == slug:
                return name
        return "Generic" if slug == DEFAULT_PROFILE_SLUG else slug
