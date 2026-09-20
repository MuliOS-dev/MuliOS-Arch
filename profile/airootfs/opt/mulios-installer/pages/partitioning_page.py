from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit
)

from widgets.toggle_switch import ToggleSwitch
from config.settings import FILESYSTEMS


class PartitioningPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(14)

        title = QLabel("Partitioning")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "MuliOS automatically creates an EFI system partition and a root partition using the selected filesystem."
            "partition plus a single root partition on the whole disk."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # -- filesystem --
        fs_label = QLabel("Root filesystem")
        fs_label.setObjectName("SectionLabel")
        layout.addWidget(fs_label)
        self.fs_combo = QComboBox()
        self.fs_combo.addItems(FILESYSTEMS)
        layout.addWidget(self.fs_combo)

        layout.addSpacing(6)

        # -- encryption --
        encrypt_row = QHBoxLayout()
        encrypt_label = QLabel("Encrypt disk (LUKS)")
        encrypt_label.setObjectName("SectionLabel")
        encrypt_row.addWidget(encrypt_label)
        encrypt_row.addStretch()
        self.encrypt_switch = ToggleSwitch(checked=False)
        self.encrypt_switch.toggled.connect(self._on_encrypt_toggled)
        encrypt_row.addWidget(self.encrypt_switch)
        layout.addLayout(encrypt_row)

        self.encrypt_password = QLineEdit()
        self.encrypt_password.setPlaceholderText("Disk encryption passphrase")
        self.encrypt_password.setEchoMode(QLineEdit.Password)
        self.encrypt_password.setEnabled(False)
        layout.addWidget(self.encrypt_password)

        layout.addSpacing(6)

        # -- swap --
        swap_row = QHBoxLayout()
        swap_label = QLabel("Enable swap")
        swap_label.setObjectName("SectionLabel")
        swap_row.addWidget(swap_label)
        swap_row.addStretch()
        self.swap_switch = ToggleSwitch(checked=True)
        swap_row.addWidget(self.swap_switch)
        layout.addLayout(swap_row)

        layout.addStretch()

    def _on_encrypt_toggled(self, checked: bool):
        self.encrypt_password.setEnabled(checked)

    def selected_filesystem(self) -> str:
        return self.fs_combo.currentText()

    def encrypt_enabled(self) -> bool:
        return self.encrypt_switch.isChecked()

    def encryption_password(self) -> str:
        return self.encrypt_password.text()

    def swap_enabled(self) -> bool:
        return self.swap_switch.isChecked()

    def validate(self) -> tuple[bool, str]:
        if self.encrypt_enabled() and len(self.encryption_password()) < 4:
            return False, "Enter an encryption passphrase (at least 4 characters)."
        return True, ""


