from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QButtonGroup

from widgets.select_card import ProfileCard
from config.settings import PROFILES, DEFAULT_PROFILE_SLUG


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

        subtitle = QLabel(
            "MuliOS installs one base system, then applies an Optimization "
            "Pack via mupdate that matches how you'll use it. You can switch "
            "profiles later with 'sudo mupdate <profile>'."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._slug_by_button = {}
        default_button = None

        for i, (slug, name, desc, icon) in enumerate(PROFILES):
            card = ProfileCard(icon, name, desc)
            row, col = divmod(i, 3)
            grid.addWidget(card, row, col)
            self.button_group.addButton(card)
            self._slug_by_button[card] = slug
            if slug == DEFAULT_PROFILE_SLUG:
                default_button = card

        layout.addLayout(grid)
        layout.addStretch()

        (default_button or list(self._slug_by_button.keys())[0]).setChecked(True)

    def selected_profile(self) -> str:
        checked = self.button_group.checkedButton()
        if checked is None:
            return DEFAULT_PROFILE_SLUG
        return self._slug_by_button[checked]

    def selected_profile_name(self) -> str:
        slug = self.selected_profile()
        for s, name, _, _ in PROFILES:
            if s == slug:
                return name
        return slug
