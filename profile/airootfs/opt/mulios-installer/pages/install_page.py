from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
)
from PySide6.QtCore import Signal

from backend.native_installer_worker import InstallWorker
from config.settings import INSTALL_LOG


class InstallPage(QWidget):
    install_finished = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Installing MuliOS...")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        self.status_label = QLabel(
            f"Installation log: {INSTALL_LOG}"
        )
        self.status_label.setObjectName("SubtitleLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(self.log_view, stretch=1)

        button_row = QHBoxLayout()

        self.view_log_button = QPushButton("View full log")
        self.view_log_button.setObjectName("SecondaryButton")
        self.view_log_button.clicked.connect(self.show_full_log)
        self.view_log_button.setEnabled(False)
        button_row.addWidget(self.view_log_button)

        button_row.addStretch()
        layout.addLayout(button_row)

        self.worker = None

    def start(self, state: dict):
        self.log_view.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText(
            f"Installation log: {INSTALL_LOG}"
        )
        self.view_log_button.setEnabled(False)

        # Create the log before the worker starts so that failures
        # during worker initialization can never leave the user
        # with a missing install log.
        try:
            log_path = Path(INSTALL_LOG)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            with log_path.open("w", encoding="utf-8") as f:
                f.write("=" * 80 + "\n")
                f.write("MuliOS Installer\n")
                f.write("=" * 80 + "\n")
                f.flush()

        except Exception as exc:
            message = (
                "Could not create the installer log: "
                f"{type(exc).__name__}: {exc}"
            )

            self.status_label.setText(
                f"Installation failed.\n{message}"
            )

            self._append_log(message)
            self.install_finished.emit(False)
            return

        self.worker = InstallWorker(state)


        self.worker.log_line.connect(self._append_log)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished_ok.connect(self._on_success)
        self.worker.failed.connect(self._on_failure)

        self.worker.start()

    def _append_log(self, text: str):
        self.log_view.append(str(text))
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_success(self):
        self.progress_bar.setValue(100)
        self.status_label.setText(
            f"Installation completed successfully.\n"
            f"Full log: {INSTALL_LOG}"
        )
        self.view_log_button.setEnabled(True)

        self._append_log("")
        self._append_log("=== Installation completed successfully ===")

        self.install_finished.emit(True)

    def _on_failure(self, error_message: str):
        self.status_label.setText(
            f"Installation failed.\n"
            f"Full log: {INSTALL_LOG}"
        )
        self.view_log_button.setEnabled(True)

        self._append_log("")
        self._append_log("=== INSTALLATION FAILED ===")
        self._append_log(str(error_message))

        self.install_finished.emit(False)

    def show_full_log(self):
        try:
            with open(INSTALL_LOG, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            if not content:
                content = "The install log is empty."

            self.log_view.setPlainText(content)

            scrollbar = self.log_view.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        except Exception as exc:
            self._append_log(f"Unable to read install log: {exc}")
