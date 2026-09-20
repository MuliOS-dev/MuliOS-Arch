import os
import subprocess
import webbrowser

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from config.settings import LOGO_PATH, INSTALL_LOG, RELEASE_NOTES_URL


class FinishedPage(QWidget):
    def __init__(self, on_reboot, on_exit, parent=None):
        super().__init__(parent)
        self._on_exit = on_exit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(18)

        logo_label = QLabel()
        if os.path.exists(LOGO_PATH):
            pixmap = QPixmap(LOGO_PATH)
            logo_label.setPixmap(pixmap.scaledToHeight(56, Qt.SmoothTransformation))
            layout.addWidget(logo_label)

        self.title = QLabel("Installation completed successfully.")
        self.title.setObjectName("TitleLabel")
        layout.addWidget(self.title)

        self.subtitle = QLabel(
            "Remove the installation media and restart to boot into MuliOS."
        )
        self.subtitle.setObjectName("SubtitleLabel")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        layout.addSpacing(10)

        button_row = QHBoxLayout()

        restart_btn = QPushButton("Restart")
        restart_btn.setObjectName("PrimaryButton")
        restart_btn.clicked.connect(on_reboot)
        button_row.addWidget(restart_btn)

        logs_btn = QPushButton("View logs")
        logs_btn.setObjectName("SecondaryButton")
        logs_btn.clicked.connect(self._view_logs)
        button_row.addWidget(logs_btn)

        notes_btn = QPushButton("Release notes")
        notes_btn.setObjectName("SecondaryButton")
        notes_btn.clicked.connect(lambda: webbrowser.open(RELEASE_NOTES_URL))
        button_row.addWidget(notes_btn)

        exit_btn = QPushButton("Exit")
        exit_btn.setObjectName("SecondaryButton")
        exit_btn.clicked.connect(self._on_exit)
        button_row.addWidget(exit_btn)

        layout.addLayout(button_row)
        layout.addStretch()

    def show_failure(self, error_message: str):
        self.title.setText("Installation failed")
        self.subtitle.setText(
            "The installer output below contains the failure details."
        )

        self.log_view = getattr(self, "log_view", None)
        if self.log_view is None:
            from PySide6.QtWidgets import QTextEdit
            self.log_view = QTextEdit()
            self.log_view.setReadOnly(True)
            self.layout().insertWidget(4, self.log_view, 1)

        self.log_view.setVisible(True)
        self.log_view.setPlainText(
            error_message or "No installer output was available."
        )

    def _view_logs(self):
        if not os.path.exists(INSTALL_LOG):
            QMessageBox.information(self, "No log yet", f"No log file found at {INSTALL_LOG}.")
            return
        try:
            subprocess.Popen(["xdg-open", INSTALL_LOG])
        except Exception:
            with open(INSTALL_LOG) as f:
                content = f.read()[-4000:]
            QMessageBox.information(self, "Install log (tail)", content)
