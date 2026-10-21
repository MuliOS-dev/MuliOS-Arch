from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QButtonGroup

from widgets.select_card import SelectCard


class DesktopPage(QWidget):
    """KDE desktop selection and optional KWin effects."""

    EFFECTS = (
        (
            "default",
            "Keep default",
            "Use the default KWin blur effect and MuliOS desktop appearance.",
        ),
        (
            "betterblur_dx",
            "Better Blur DX",
            "Adds force blur, adjustable blur appearance and rounded corners.",
        ),
        (
            "glass",
            "KWin Effects Glass",
            "Adds a glass-like blur effect with tint, glow and rounded corners.",
        ),
    )

    PLUGIN_DIRS = (
        Path("/usr/lib/qt6/plugins/kwin/effects/plugins"),
        Path("/usr/lib/kwin/plugins"),
        Path("/usr/lib/x86_64-linux-gnu/qt6/plugins/kwin/effects/plugins"),
    )

    PLUGIN_TOKENS = {
        "betterblur_dx": ("better_blur_dx",),
        "glass": ("glass",),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Desktop environment")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "MuliOS uses KDE Plasma. Select an optional KWin visual effect, "
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
            card = SelectCard("", name, description)
            grid.addWidget(card, index // 2, index % 2)
            self.effect_group.addButton(card)
            self._effect_by_button[card] = slug
            if slug == "default":
                card.setChecked(True)

        layout.addLayout(grid)
        self.status_label = QLabel("")
        self.status_label.setObjectName("SubtitleLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()

    def selected_desktop(self):
        return "kde"

    def selected_effect(self):
        checked = self.effect_group.checkedButton()
        return self._effect_by_button.get(checked, "default")

    @classmethod
    def installed_effects(cls):
        installed = set()
        for effect, tokens in cls.PLUGIN_TOKENS.items():
            if any(
                directory.is_dir()
                and any(
                    token in plugin.name.lower()
                    for plugin in directory.glob("*.so")
                    for token in tokens
                )
                for directory in cls.PLUGIN_DIRS
            ):
                installed.add(effect)
        return installed

    def refresh_effects(self):
        installed = self.installed_effects()
        labels = {
            "betterblur_dx": "Better Blur DX",
            "glass": "KWin Effects Glass",
        }
        if installed:
            names = ", ".join(labels[item] for item in sorted(installed))
            self.status_label.setText(
                f"Detected in this live session: {names}. "
                "Preview can load these effects now."
            )
        else:
            self.status_label.setText(
                "No optional KWin effect plugin was detected in the live session. "
                "Refresh checks the local ISO; selected effects can still be built "
                "for the installed system during installation."
            )
        return installed
