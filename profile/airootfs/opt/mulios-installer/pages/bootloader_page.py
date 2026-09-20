from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox

from config.settings import BOOTLOADERS


class BootloaderPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Bootloader")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "GRUB works everywhere (BIOS and UEFI). Systemd-boot and Limine "
            "are lighter but UEFI-only."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.bootloader_combo = QComboBox()
        self.bootloader_combo.addItems(BOOTLOADERS)
        layout.addWidget(self.bootloader_combo)

        layout.addStretch()

    def selected_bootloader(self) -> str:
        return self.bootloader_combo.currentText()
