#!/usr/bin/env python3

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import gettempdir

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView

BASE_DIR = Path(__file__).resolve().parent
BACKEND = BASE_DIR / "main.js"
URL = "http://127.0.0.1:4700"
BACKEND_START_TIMEOUT = 8.0


def backend_is_ready():
    try:
        with urllib.request.urlopen(URL, timeout=0.25) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


class TaskManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MuliOS Task Manager")
        self.resize(1200, 800)
        self.backend = None

        log_candidates = []
        xdg_state_home = os.environ.get("XDG_STATE_HOME")
        if xdg_state_home:
            log_candidates.append(Path(xdg_state_home) / "mulios")
        log_candidates.append(Path.home() / ".local" / "state" / "mulios")
        log_candidates.append(Path(gettempdir()) / f"mulios-state-{os.getuid()}")

        self._backend_log = None
        log_errors = []
        for log_dir in log_candidates:
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                self._backend_log = (log_dir / "taskmanager-backend.log").open(
                    "a", encoding="utf-8"
                )
                break
            except OSError as exc:
                log_errors.append(f"{log_dir}: {exc}")

        if self._backend_log is None:
            raise RuntimeError(
                "Could not create a writable Task Manager log file. "
                + "; ".join(log_errors)
            )
        self._backend_log.write("\n--- Task Manager backend starting ---\n")
        self._backend_log.flush()

        try:
            self.backend = subprocess.Popen(
                ["/usr/bin/node", str(BACKEND)],
                cwd=str(BASE_DIR),
                stdout=self._backend_log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            self._backend_log.write(f"Could not start Node.js backend: {exc}\n")
            self._backend_log.flush()
            self._backend_log.close()
            raise RuntimeError(
                "Could not start the Task Manager Node.js backend. "
                "Check the Task Manager backend log in ~/.local/state/mulios or /tmp."
            ) from exc

        deadline = time.monotonic() + BACKEND_START_TIMEOUT
        ready = False
        while time.monotonic() < deadline:
            if self.backend.poll() is not None:
                break
            if backend_is_ready():
                ready = True
                break
            time.sleep(0.1)

        if not ready:
            status = self.backend.poll()
            self._stop_backend()
            self._backend_log.flush()
            self._backend_log.close()
            raise RuntimeError(
                "The Task Manager backend did not become ready within "
                f"{BACKEND_START_TIMEOUT:.0f} seconds (exit status: {status}). "
                "Check ~/.local/state/mulios/taskmanager-backend.log."
            )

        try:
            self.browser = QWebEngineView()
            self.browser.setUrl(QUrl(URL))
            self.setCentralWidget(self.browser)
        except Exception:
            self._stop_backend()
            self._backend_log.flush()
            self._backend_log.close()
            raise

    def _stop_backend(self):
        if self.backend is not None and self.backend.poll() is None:
            self.backend.terminate()
            try:
                self.backend.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.backend.kill()
                self.backend.wait(timeout=2)

    def closeEvent(self, event):
        self._stop_backend()
        if not self._backend_log.closed:
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
