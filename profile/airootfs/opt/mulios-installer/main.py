"""
main.py - MuliOS Arch Installer

Run with:
    sudo python3 main.py
"""

import os
import sys
import traceback
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QLabel, QPushButton, QMessageBox
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt

from theme import stylesheet
from config.settings import LOGO_PATH, APP_NAME, DISTRO_NAME, DEFAULT_PROFILE_SLUG


def ensure_root():
    """Re-exec the installer as root when launched by the live user."""
    if os.geteuid() == 0:
        return

    sudo = "/usr/bin/sudo"

    if not os.path.exists(sudo):
        raise RuntimeError(
            "The MuliOS Installer must run as root, but sudo is not available."
        )

    command = [
        sudo,
        "-n",
        sys.executable,
        os.path.abspath(__file__),
        *sys.argv[1:],
    ]

    os.execv(sudo, command)

from pages.welcome_page import WelcomePage
from pages.language_page import LanguagePage
from pages.keyboard_page import KeyboardPage
from pages.timezone_page import TimezonePage
from pages.network_page import NetworkPage
from pages.disk_page import DiskPage
from pages.partitioning_page import PartitioningPage
from pages.bootloader_page import BootloaderPage
from pages.account_page import AccountPage
from pages.desktop_page import DesktopPage
from pages.packages_page import PackagesPage
from pages.profile_page import ProfilePage
from pages.advanced_page import AdvancedPage
from pages.summary_page import SummaryPage
from pages.install_page import InstallPage
from pages.finished_page import FinishedPage

STEP_NAMES = [
    "Welcome", "Language", "Keyboard", "Timezone", "Network",
    "Disk", "Partitioning", "Bootloader", "Account", "Desktop",
    "Packages", "Profile", "Advanced", "Summary", "Install", "Finished",
]

# Index of key steps, for readability in navigation logic below
IDX_WELCOME, IDX_LANGUAGE, IDX_KEYBOARD, IDX_TIMEZONE, IDX_NETWORK = 0, 1, 2, 3, 4
IDX_DISK, IDX_PARTITION, IDX_BOOTLOADER, IDX_ACCOUNT, IDX_DESKTOP = 5, 6, 7, 8, 9
IDX_PACKAGES, IDX_PROFILE, IDX_ADVANCED, IDX_SUMMARY = 10, 11, 12, 13
IDX_INSTALL, IDX_FINISHED = 14, 15


class Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(190)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 26, 20, 26)
        layout.setSpacing(10)

        logo_label = QLabel()
        if os.path.exists(LOGO_PATH):
            pixmap = QPixmap(LOGO_PATH)
            logo_label.setPixmap(pixmap.scaledToHeight(32, Qt.SmoothTransformation))
        else:
            logo_label.setText(DISTRO_NAME)
            logo_label.setStyleSheet("font-size: 13pt; font-weight: 700; color: white;")
        layout.addWidget(logo_label)
        layout.addSpacing(14)

        self.step_labels = []
        for name in STEP_NAMES:
            lbl = QLabel(name)
            lbl.setStyleSheet("font-size: 9pt;")
            layout.addWidget(lbl)
            self.step_labels.append(lbl)

        layout.addStretch()

    def set_active_step(self, index: int):
        for i, lbl in enumerate(self.step_labels):
            lbl.setProperty("stepActive", i == index)
            lbl.setProperty("stepDone", i < index)
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)


class MuliOSInstaller(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(980, 640)
        if os.path.exists(LOGO_PATH):
            self.setWindowIcon(QIcon(LOGO_PATH))

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = Sidebar()
        root_layout.addWidget(self.sidebar)

        content_wrapper = QWidget()
        content_wrapper.setObjectName("ContentPanel")
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(content_wrapper, stretch=1)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, stretch=1)

        # -- pages --
        self.welcome_page = WelcomePage()
        self.language_page = LanguagePage()
        self.keyboard_page = KeyboardPage()
        self.timezone_page = TimezonePage()
        self.network_page = NetworkPage()
        self.disk_page = DiskPage()
        self.partitioning_page = PartitioningPage()
        self.bootloader_page = BootloaderPage()
        self.account_page = AccountPage()
        self.desktop_page = DesktopPage()
        self.packages_page = PackagesPage()
        self.profile_page = ProfilePage()
        self.advanced_page = AdvancedPage()
        self.summary_page = SummaryPage()
        self.install_page = InstallPage()
        self.finished_page = FinishedPage(on_reboot=self.reboot_system, on_exit=self.close)

        for page in (
            self.welcome_page, self.language_page, self.keyboard_page, self.timezone_page,
            self.network_page, self.disk_page, self.partitioning_page, self.bootloader_page,
            self.account_page, self.desktop_page, self.packages_page, self.profile_page,
            self.advanced_page, self.summary_page, self.install_page, self.finished_page,
        ):
            self.stack.addWidget(page)

        self.install_page.install_finished.connect(self._on_install_finished)

        # -- nav bar --
        nav_bar = QWidget()
        nav_bar.setObjectName("NavBar")
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(20, 12, 20, 20)

        self.back_button = QPushButton("Back")
        self.back_button.setObjectName("SecondaryButton")
        self.back_button.clicked.connect(self.go_back)
        nav_layout.addWidget(self.back_button)
        nav_layout.addStretch()

        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("PrimaryButton")
        self.next_button.clicked.connect(self.go_next)
        nav_layout.addWidget(self.next_button)

        content_layout.addWidget(nav_bar)

        QApplication.instance().setStyleSheet(stylesheet())
        self._goto_step(0)

    # -- navigation ----------------------------------------------------------

    def _goto_step(self, index: int):
        self.stack.setCurrentIndex(index)
        self.sidebar.set_active_step(index)
        self.back_button.setEnabled(0 < index < IDX_INSTALL)
        self.next_button.setVisible(index < IDX_INSTALL)

        if index == IDX_SUMMARY:
            self.next_button.setText("Install")
            self.summary_page.set_state(
                self._collect_install_state(), self.network_page.is_connected()
            )
        else:
            self.next_button.setText("Next")

    def go_back(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self._goto_step(idx - 1)

    def go_next(self):
        idx = self.stack.currentIndex()

        if idx == IDX_DISK:
            if not self.disk_page.selected_disk():
                QMessageBox.warning(self, "No disk selected", "Please select a disk to continue.")
                return

        elif idx == IDX_PARTITION:
            ok, msg = self.partitioning_page.validate()
            if not ok:
                QMessageBox.warning(self, "Check partitioning options", msg)
                return

        elif idx == IDX_ACCOUNT:
            if not self.account_page.validate():
                return

        elif idx == IDX_SUMMARY:
            self._confirm_and_install()
            return

        if idx < IDX_INSTALL:
            self._goto_step(idx + 1)

    # -- state collection -----------------------------------------------------

    def _collect_install_state(self) -> dict:
        return {
            "locale": self.language_page.selected_locale(),
            "locale_display_name": self.language_page.selected_locale(),
            "keyboard_layout": self.keyboard_page.selected_layout(),
            "timezone": self.timezone_page.selected_timezone(),
            "network_mode": self.network_page.network_mode(),
            "disk": self.disk_page.selected_disk(),
            "filesystem": self.partitioning_page.selected_filesystem(),
            "encrypt_disk": self.partitioning_page.encrypt_enabled(),
            "encryption_password": self.partitioning_page.encryption_password(),
            "enable_swap": self.partitioning_page.swap_enabled(),
            "bootloader": self.bootloader_page.selected_bootloader(),
            **self.account_page.data(),
            "desktop_environment": self.desktop_page.selected_desktop(),
            "extra_packages": self.packages_page.selected_packages(),
            "profile": self.profile_page.selected_profile(),
            "profile_name": self.profile_page.selected_profile_name(),
            "mirror_region": self.advanced_page.mirror_region(),
            "kernel": self.advanced_page.kernel(),
            "enable_multilib": self.advanced_page.multilib_enabled(),
            "parallel_downloads": self.advanced_page.parallel_downloads(),
            "skip_mupdate": not self.network_page.is_connected(),
        }

    def _confirm_and_install(self):
        disk = self.disk_page.selected_disk()
        reply = QMessageBox.warning(
            self, "Confirm installation",
            f"This will ERASE ALL DATA on {disk}.\n\nThis action cannot be undone. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        state = self._collect_install_state()
        self._goto_step(IDX_INSTALL)
        self.install_page.start(state)

    def _on_install_finished(self, success: bool):
        # Capture the installer output before changing pages.
        # The QTextEdit remains available even if the filesystem
        # log becomes inaccessible during cleanup.
        live_log = ""

        try:
            live_log = self.install_page.log_view.toPlainText()
        except Exception:
            live_log = ""

        if success:
            self._goto_step(IDX_FINISHED)
            return

        self._goto_step(IDX_FINISHED)

        failure_text = ""
        log_text = live_log

        # Prefer the live in-memory log, then fall back to the
        # persistent filesystem log.
        if log_text.strip():
            marker = "=== INSTALLATION FAILED ==="

            if marker in log_text:
                failure_text = log_text.split(
                    marker,
                    1,
                )[1].strip()

            if not failure_text:
                failure_text = log_text.strip()

        if not failure_text:
            try:
                log_path = Path("/var/log/mulios/install.log")

                if log_path.exists():
                    log_text = log_path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    )

                    marker = "=== INSTALLATION FAILED ==="

                    if marker in log_text:
                        failure_text = log_text.split(
                            marker,
                            1,
                        )[1].strip()
                    else:
                        failure_text = log_text.strip()

            except Exception as exc:
                failure_text = (
                    "The installation failed. "
                    f"Could not read the failure log: {exc}"
                )

        if not failure_text:
            failure_text = (
                "The installation failed, but no installer "
                "output was available."
            )

        self.finished_page.show_failure(
            failure_text
        )

    def reboot_system(self):
        reply = QMessageBox.question(
            self, "Restart", "Restart the computer now?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            import subprocess
            subprocess.run(["reboot"])


def main():
    ensure_root()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(
                exc_type,
                exc_value,
                exc_traceback,
            )
            return

        try:
            log_path = Path(
                "/var/log/mulios/install.log"
            )

            log_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with log_path.open(
                "a",
                encoding="utf-8",
            ) as f:
                f.write("\n")
                f.write("=" * 80 + "\n")
                f.write("=== UNHANDLED INSTALLER EXCEPTION ===\n")
                f.write(
                    "".join(
                        traceback.format_exception(
                            exc_type,
                            exc_value,
                            exc_traceback,
                        )
                    )
                )
                f.write("=" * 80 + "\n")

        except Exception:
            pass

        QMessageBox.critical(
            None,
            "MuliOS Installer Error",
            "An unexpected error occurred.\n\n"
            "The full Python traceback was written to:\n"
            "/var/log/mulios/install.log",
        )

    sys.excepthook = handle_exception

    window = MuliOSInstaller()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
