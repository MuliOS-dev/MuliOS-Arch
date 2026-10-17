from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QButtonGroup

from widgets.select_card import SelectCard


EFFECT_OPTIONS = [
    (
        "default",
        "Keep default",
        "Keep the standard KDE Plasma blur effect. No additional effect is installed.",
        "",
    ),
    (
        "forceblur",
        "Better Blur",
        "A Plasma blur-effect fork with forced blur, rounded corners, and additional controls.",
        "",
    ),
    (
        "glass",
        "KWin Effects Glass",
        "A blur-effect fork with tint, glow, edge lighting, and refraction features.",
        "",
    ),
]


class DesktopPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Desktop environment")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "MuliOS uses KDE Plasma. Optionally choose one alternative blur "
            "effect, or keep the default. Only the selected effect will be installed."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        desktop_card = QLabel("KDE Plasma")
        desktop_card.setObjectName("FixedChoiceCard")
        layout.addWidget(desktop_card)

        effect_title = QLabel("Desktop effects")
        effect_title.setObjectName("SectionLabel")
        layout.addWidget(effect_title)

        self.effect_group = QButtonGroup(self)
        self.effect_group.setExclusive(True)
        self._effect_by_button = {}
        grid = QGridLayout()
        grid.setSpacing(14)

        for index, (slug, name, description, icon) in enumerate(EFFECT_OPTIONS):
            card = SelectCard(icon, name, description)
            grid.addWidget(card, index // 2, index % 2)
            self.effect_group.addButton(card)
            self._effect_by_button[card] = slug
            if slug == "default":
                card.setChecked(True)

        layout.addLayout(grid)
        layout.addStretch()

    def selected_desktop(self):
        return "kde"

    def selected_effect(self) -> str:
        checked = self.effect_group.checkedButton()
        if checked is None:
            return "default"
        return self._effect_by_button.get(checked, "default")
