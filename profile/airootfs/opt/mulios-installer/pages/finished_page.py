import os
import subprocess
import webbrowser

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
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
        layout.setSpacing(14)

        logo_label = QLabel()

        if os.path.exists(LOGO_PATH):
            pixmap = QPixmap(LOGO_PATH)
            logo_label.setPixmap(
                pixmap.scaledToHeight(56, Qt.SmoothTransformation)
            )
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

        self.log_path_label = QLabel(
            f"Install log: {INSTALL_LOG}"
        )
        self.log_path_label.setObjectName("SubtitleLabel")
        self.log_path_label.setWordWrap(True)
        layout.addWidget(self.log_path_label)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        self.log_view.setVisible(False)
        layout.addWidget(self.log_view, stretch=1)

        button_row = QHBoxLayout()

        self.restart_button = QPushButton("Restart")
        self.restart_button.setObjectName("PrimaryButton")
        self.restart_button.clicked.connect(on_reboot)
        button_row.addWidget(self.restart_button)

        self.logs_button = QPushButton("View logs")
        self.logs_button.setObjectName("SecondaryButton")
        self.logs_button.clicked.connect(self._view_logs)
        button_row.addWidget(self.logs_button)

        self.notes_button = QPushButton("Release notes")
        self.notes_button.setObjectName("SecondaryButton")
        self.notes_button.clicked.connect(
            lambda: webbrowser.open(RELEASE_NOTES_URL)
        )
        button_row.addWidget(self.notes_button)

        self.exit_button = QPushButton("Exit")
        self.exit_button.setObjectName("SecondaryButton")
        self.exit_button.clicked.connect(self._on_exit)
        button_row.addWidget(self.exit_button)

        layout.addLayout(button_row)

        self._showing_failure = False

    def show_failure(self, error_message: str):
        self._showing_failure = True

        self.title.setText("Installation failed")

        self.subtitle.setText(
            "MuliOS could not be installed.\n\n"
            "The installer output below contains the failure details."
        )

        self.log_path_label.setText(
            f"Install log: {INSTALL_LOG}"
        )

        # Always show the captured installer output immediately.
        # This avoids losing the diagnostic information when the
        # filesystem log is unavailable after cleanup.
        self.log_view.setVisible(True)
        self.log_view.setPlainText(
            error_message or
            "No installer output was available."
        )

        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _view_logs(self):
        self.log_view.setVisible(True)

        try:
            with open(
                INSTALL_LOG,
                "r",
                encoding="utf-8",
                errors="replace",
            ) as f:
                content = f.read()

            if not content:
                content = "The install log is empty."

            self.log_view.setPlainText(content)

        except Exception as exc:
            self.log_view.setPlainText(
                f"Unable to read install log:\n\n{exc}"
            )

        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
