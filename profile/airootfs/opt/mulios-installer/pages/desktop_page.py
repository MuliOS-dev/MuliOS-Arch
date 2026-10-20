from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QButtonGroup

from widgets.select_card import SelectCard


class DesktopPage(QWidget):
    """Keep the fixed KDE desktop choice and optionally select one KWin effect."""


    EFFECTS = (
        (
            "default",
            "Keep default",
            "Do not install an additional KWin effect. Keep the default MuliOS desktop.",
        ),
        (
            "betterblur_dx",
            "Better Blur DX (Force Blur)",
            "Adds force blur, adjustable blur appearance, rounded corners and refraction. Built for the KWin version in this ISO.",
        ),
        (
            "glass",
            "KWin Effects Glass",
            "Adds the Glass effect for a translucent, glass-like desktop appearance.",
        ),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Desktop environment")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "MuliOS uses KDE Plasma. Optionally choose one KWin visual effect, "
            "or keep the default desktop configuration."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        desktop_card = QLabel("KDE Plasma")
        desktop_card.setObjectName("FixedChoiceCard")
        layout.addWidget(desktop_card)

        effects_title = QLabel("Optional desktop effect")
        effects_title.setObjectName("SectionLabel")
        layout.addWidget(effects_title)

        self.effect_group = QButtonGroup(self)
        self.effect_group.setExclusive(True)
        self._effect_by_button = {}
        grid = QGridLayout()
        grid.setSpacing(14)

        for index, (slug, name, description) in enumerate(self.EFFECTS):
            # Screenshots can be added to these cards later without changing
            # the installer-wide theme or navigation.
            card = SelectCard("", name, description)
            grid.addWidget(card, index // 2, index % 2)
            self.effect_group.addButton(card)
            self._effect_by_button[card] = slug
            if slug == "default":
                card.setChecked(True)

        layout.addLayout(grid)
        layout.addStretch()

    def selected_desktop(self):
        return "kde"

    def selected_effect(self):
        checked = self.effect_group.checkedButton()
        return self._effect_by_button.get(checked, "default")
