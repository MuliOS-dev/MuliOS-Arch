from pathlib import Path
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar, QTextEdit
from PySide6.QtCore import Signal

from backend.native_installer_worker import InstallWorker
from config.settings import INSTALL_LOG


class InstallPage(QWidget):
    install_finished = Signal(bool)  # True = success, False = failed

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Installing MuliOS...")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel(f"Full log is also being written to {INSTALL_LOG}")
        subtitle.setObjectName("SubtitleLabel")
        layout.addWidget(subtitle)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, stretch=1)

        self.worker = None

    def start(self, state: dict):
        self.log_view.clear()
        self.progress_bar.setValue(0)

        # The installer is always elevated by main.py before this page
        # can be reached. Create the persistent log up front so failures
        # during worker startup are still visible to the user.
        try:
            log_path = Path(INSTALL_LOG)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                "=" * 80 + "\\n"
                "MuliOS Installer\\n"
                "=" * 80 + "\\n",
                encoding="utf-8",
            )
        except Exception as exc:
            message = (
                "Could not create the installer log: "
                f"{type(exc).__name__}: {exc}"
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
        self.log_view.append(text)

    def _on_success(self):
        self._append_log("Installation completed successfully.")
        self.install_finished.emit(True)

    def _on_failure(self, error_message: str):
        self._append_log(f"ERROR: {error_message}")
        self.install_finished.emit(False)

