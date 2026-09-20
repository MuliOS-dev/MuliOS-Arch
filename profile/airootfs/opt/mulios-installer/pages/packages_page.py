from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit


class PackagesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Additional packages")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "Optional: list any extra pacman packages to install, space-separated "
            "(e.g. neovim htop firefox). Your MuliOS profile, chosen next, adds "
            "its own software on top of this automatically."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.packages_edit = QTextEdit()
        self.packages_edit.setPlaceholderText("neovim htop firefox ...")
        layout.addWidget(self.packages_edit, stretch=1)

    def selected_packages(self) -> list[str]:
        text = self.packages_edit.toPlainText().strip()
        return text.split() if text else []
