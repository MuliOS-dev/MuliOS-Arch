#!/usr/bin/env python3

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView


HTML = Path("/opt/taskmanager/index.html")


class TaskManager(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MuliOS Task Manager")
        self.resize(1200, 760)

        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl.fromLocalFile(str(HTML)))
        self.setCentralWidget(self.browser)


def main():
    app = QApplication(sys.argv)

    window = TaskManager()
    window.show()

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
