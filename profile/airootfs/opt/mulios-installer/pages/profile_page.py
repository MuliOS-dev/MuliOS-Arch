import os
import re
import subprocess

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QButtonGroup, QPushButton,
)

from widgets.select_card import ProfileCard
from config.settings import PROFILE_DESCRIPTIONS, DEFAULT_PROFILE_SLUG

PROFILE_ORDER = ("gaming", "code", "ai", "study", "privacy", "casual")


def _available_profiles():
    """Read available profiles from the local MuliOS profile manager."""
    if os.name != "posix":
        return list(PROFILE_ORDER)

    result = subprocess.run(
        ["sudo", "mulios-profile", "list"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    output = f"{result.stdout}\n{result.stderr}".lower()
    available = [
        slug for slug in PROFILE_ORDER
        if re.search(rf"\\b{re.escape(slug)}\\b", output)
    ]
    if not available:
        raise RuntimeError(
            "mulios-profile list did not return any recognized profiles."
        )
    return available


class _ProfileFetchWorker(QObject):
    loaded = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            self.loaded.emit(_available_profiles())
        except Exception as exc:
            self.failed.emit(str(exc))


class ProfilePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("How will you primarily use this computer?")
        title.setObjectName("TitleLabel")
        title.setWordWrap(True)
        layout.addWidget(title)

        self.subtitle = QLabel("Available profiles are read from mulios-profile.")
        self.subtitle.setObjectName("SubtitleLabel")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        self.refresh_button = QPushButton("Refresh profiles")
        self.refresh_button.setObjectName("SecondaryButton")
        self.refresh_button.clicked.connect(self.refresh_profiles)

        self.grid = QGridLayout()
        self.grid.setSpacing(14)
        layout.addLayout(self.grid)
        layout.addStretch()

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._slug_by_button = {}
        self._name_by_slug = {}
        self._available_slugs = []
        self._refresh_thread = None
        self._refresh_worker = None
        self.refresh_profiles(initial=True)

    def _render_profiles(self, slugs):
        previous = self.selected_profile() if self._slug_by_button else DEFAULT_PROFILE_SLUG

        for button in self.button_group.buttons():
            self.button_group.removeButton(button)
            self.grid.removeWidget(button)
            button.deleteLater()

        self._slug_by_button = {}
        self._name_by_slug = {}
        self._available_slugs = list(slugs)

        for i, slug in enumerate(self._available_slugs):
            name, description = PROFILE_DESCRIPTIONS[slug]
            card = ProfileCard("", name, description)
            row, col = divmod(i, 3)
            self.grid.addWidget(card, row, col)
            self.button_group.addButton(card)
            self._slug_by_button[card] = slug
            self._name_by_slug[slug] = name

        selected = previous if previous in self._available_slugs else self._available_slugs[0]
        for button, slug in self._slug_by_button.items():
            button.setChecked(slug == selected)

    def refresh_profiles(self, initial=False):
        if self._refresh_thread is not None:
            return

        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Checking..." if initial else "Refreshing...")
        self.subtitle.setText("Running sudo mulios-profile list...")

        thread = QThread(self)
        worker = _ProfileFetchWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.loaded.connect(self._profiles_loaded)
        worker.failed.connect(self._profiles_failed)
        worker.loaded.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._refresh_finished)
        thread.finished.connect(thread.deleteLater)
        self._refresh_thread = thread
        self._refresh_worker = worker
        thread.start()

    def _profiles_loaded(self, discovered):
        self._render_profiles(discovered)
        self.subtitle.setText(f"Loaded {len(discovered)} profiles from mulios-profile.")
        self.refresh_button.setText("Refresh profiles")
        self.refresh_button.setEnabled(True)

    def _profiles_failed(self, error):
        self.subtitle.setText(f"Could not list MuliOS profiles: {error}")
        self.refresh_button.setText("Retry profiles")
        self.refresh_button.setEnabled(True)

    def _refresh_finished(self):
        self._refresh_thread = None
        self._refresh_worker = None

    def selected_profile(self) -> str:
        checked = self.button_group.checkedButton()
        return self._slug_by_button.get(checked, DEFAULT_PROFILE_SLUG)

    def selected_profile_name(self) -> str:
        slug = self.selected_profile()
        return self._name_by_slug.get(slug, PROFILE_DESCRIPTIONS[DEFAULT_PROFILE_SLUG][0])

    def available_profiles(self):
        return list(self._available_slugs)
