from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


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
            "MuliOS uses KDE Plasma as its desktop environment."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        card = QLabel("KDE Plasma")
        card.setObjectName("FixedChoiceCard")
        layout.addWidget(card)

        layout.addStretch()

    def selected_desktop(self):
        return "kde"
