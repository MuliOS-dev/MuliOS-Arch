#!/usr/bin/env python3

import signal
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtWebEngineWidgets import QWebEngineView

BASE_DIR = Path(__file__).resolve().parent
BACKEND = BASE_DIR / "main.js"
URL = "http://127.0.0.1:4700"


class TaskManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Task Manager")
        self.resize(1200, 800)

        self.backend = subprocess.Popen(
            ["node", str(BACKEND)],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

        time.sleep(1)

        if self.backend.poll() is not None:
            QMessageBox.critical(
                self,
                "Task Manager",
                "The Task Manager backend failed to start.",
            )
            raise RuntimeError("Node.js backend exited")

        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl(URL))
        self.setCentralWidget(self.browser)

    def closeEvent(self, event):
        if self.backend.poll() is None:
            self.backend.terminate()
            try:
                self.backend.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.backend.kill()
        event.accept()


def main():
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    window = TaskManager()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
