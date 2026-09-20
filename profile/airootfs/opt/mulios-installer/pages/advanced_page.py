from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox

from widgets.toggle_switch import ToggleSwitch

COMMON_MIRROR_REGIONS = [
    "Worldwide", "United States", "Germany", "France", "United Kingdom",
    "Canada", "Australia", "Japan", "Brazil", "India",
]
KERNELS = ["linux", "linux-lts", "linux-zen", "linux-hardened"]


class AdvancedPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(14)

        title = QLabel("Advanced options")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "These settings control how MuliOS configures the installed system. "
            "The defaults are suitable for most people."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # -- mirror region --
        mirror_label = QLabel("Mirror region")
        mirror_label.setObjectName("SectionLabel")
        layout.addWidget(mirror_label)
        self.mirror_combo = QComboBox()
        self.mirror_combo.setEditable(True)
        self.mirror_combo.addItems(COMMON_MIRROR_REGIONS)
        layout.addWidget(self.mirror_combo)

        layout.addSpacing(6)

        # -- kernel --
        kernel_label = QLabel("Kernel")
        kernel_label.setObjectName("SectionLabel")
        layout.addWidget(kernel_label)
        self.kernel_combo = QComboBox()
        self.kernel_combo.addItems(KERNELS)
        layout.addWidget(self.kernel_combo)

        layout.addSpacing(6)

        # -- multilib --
        multilib_row = QHBoxLayout()
        multilib_label = QLabel("Enable multilib (32-bit libraries, needed for some games/Wine)")
        multilib_label.setObjectName("SectionLabel")
        multilib_row.addWidget(multilib_label)
        multilib_row.addStretch()
        self.multilib_switch = ToggleSwitch(checked=True)
        multilib_row.addWidget(self.multilib_switch)
        layout.addLayout(multilib_row)

        layout.addSpacing(6)

        # -- parallel downloads --
        parallel_row = QHBoxLayout()
        parallel_label = QLabel("Parallel pacman downloads")
        parallel_label.setObjectName("SectionLabel")
        parallel_row.addWidget(parallel_label)
        parallel_row.addStretch()
        self.parallel_spin = QSpinBox()
        self.parallel_spin.setRange(1, 20)
        self.parallel_spin.setValue(5)
        parallel_row.addWidget(self.parallel_spin)
        layout.addLayout(parallel_row)

        layout.addStretch()

    def mirror_region(self) -> str:
        return self.mirror_combo.currentText().strip() or "Worldwide"

    def kernel(self) -> str:
        return self.kernel_combo.currentText()

    def multilib_enabled(self) -> bool:
        return self.multilib_switch.isChecked()

    def parallel_downloads(self) -> int:
        return self.parallel_spin.value()


