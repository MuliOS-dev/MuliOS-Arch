#!/usr/bin/env python3

import os
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

        log_dir = Path.home() / ".local" / "state" / "mulios"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._backend_log = (log_dir / "taskmanager-backend.log").open(
            "a", encoding="utf-8"
        )
        self._backend_log.write("\n--- Task Manager backend starting ---\n")
        self._backend_log.flush()

        self.backend = subprocess.Popen(
            ["node", str(BACKEND)],
            cwd=str(BASE_DIR),
            stdout=self._backend_log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Node can take longer to initialize on slower live USBs or VMs.
        deadline = time.monotonic() + 5
        while self.backend.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)

        if self.backend.poll() is not None:
            self._backend_log.flush()
            QMessageBox.critical(
                self,
                "Task Manager",
                "The Task Manager backend failed to start. "
                "See ~/.local/state/mulios/taskmanager-backend.log.",
            )
            self._backend_log.close()
            raise RuntimeError("Node.js backend exited; see taskmanager-backend.log")

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
        self._backend_log.flush()
        self._backend_log.close()
        event.accept()


def main():
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    window = TaskManager()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
