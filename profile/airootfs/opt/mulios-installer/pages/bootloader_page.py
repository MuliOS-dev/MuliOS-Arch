from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class BootloaderPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Bootloader")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "MuliOS installs GRUB as its bootloader."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        card = QLabel("GRUB")
        card.setObjectName("FixedChoiceCard")
        layout.addWidget(card)

        layout.addStretch()

    def selected_bootloader(self) -> str:
        return "grub"
