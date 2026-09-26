#!/usr/bin/env python3

import signal
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtWebEngineWidgets import QWebEngineView


BASE_DIR = Path(__file__).resolve().parent
HTML = BASE_DIR / "index.html"
BACKEND = BASE_DIR / "backend" / "taskmanager"


class TaskManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Task Manager")
        self.resize(1200, 800)
        self.backend = None

        if not BACKEND.is_file():
            QMessageBox.critical(
                self,
                "Task Manager",
                "The native C backend is missing. Rebuild the MuliOS ISO.",
            )
            raise RuntimeError(f"Missing native backend: {BACKEND}")

        self.backend = subprocess.Popen(
            [str(BACKEND)],
            cwd=str(BASE_DIR),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl.fromLocalFile(str(HTML)))
        self.setCentralWidget(self.browser)

    def closeEvent(self, event):
        if self.backend and self.backend.poll() is None:
            self.backend.terminate()
            try:
                self.backend.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.backend.kill()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    window = TaskManager()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
