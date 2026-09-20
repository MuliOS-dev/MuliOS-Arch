import os

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QMessageBox
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from config.settings import LOGO_PATH, DISTRO_NAME, APP_NAME, VERSION_STRING


class WelcomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(18)

        top_row = QHBoxLayout()
        logo_label = QLabel()
        if os.path.exists(LOGO_PATH):
            pixmap = QPixmap(LOGO_PATH)
            logo_label.setPixmap(pixmap.scaledToHeight(64, Qt.SmoothTransformation))
        else:
            logo_label.setText(DISTRO_NAME)
            logo_label.setObjectName("TitleLabel")
        top_row.addWidget(logo_label)
        top_row.addStretch()

        about_btn = QPushButton("About")
        about_btn.setObjectName("SecondaryButton")
        about_btn.clicked.connect(self._show_about)
        top_row.addWidget(about_btn)
        layout.addLayout(top_row)

        layout.addSpacing(16)

        title = QLabel(f"Welcome to {DISTRO_NAME}")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "This wizard will install MuliOS Arch on this computer using "
            "MuliOS Installer, MUpdate and system recovery."
            "MuliOS will set your machine up and optimize it for dedicated use. for more info, "
            "check our docs."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignLeft)
        layout.addWidget(subtitle)

        layout.addStretch()

    def _show_about(self):
        QMessageBox.information(
            self, f"About {APP_NAME}",
            f"{APP_NAME}\n{VERSION_STRING}\n\n"
            f"{DISTRO_NAME} is built on Arch Linux. This installer is a "
            "native installer for MuliOS - it does not reimplement Arch "
            "installation logic. Post-install profile setup is handled "
            "by mupdate and update.",
        )

