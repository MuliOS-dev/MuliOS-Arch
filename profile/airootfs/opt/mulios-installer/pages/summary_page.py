from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit
)


class SummaryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Ready to install")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        warning = QLabel(
            "Review your choices below. Clicking Install erases the selected "
            "disk and cannot be undone."
        )
        warning.setObjectName("SubtitleLabel")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        self.summary_box = QTextEdit()
        self.summary_box.setReadOnly(True)
        layout.addWidget(self.summary_box, stretch=1)

        self._state = None

    def set_state(self, state: dict, internet_connected: bool):
        self._state = dict(state)
        self._state["_internet_connected"] = internet_connected
        self._render_summary(self._state, internet_connected)

    def _render_summary(self, state: dict, internet_connected: bool):
        lines = [
            f"Disk to erase:        {state.get('disk', '(none)')}",
            f"Filesystem:           {state.get('filesystem', 'ext4')}",
            f"Encryption:           {'Enabled' if state.get('encrypt_disk') else 'Disabled'}",
            f"Swap:                 {'Enabled' if state.get('enable_swap') else 'Disabled'}",
            f"Bootloader:           {state.get('bootloader', 'Grub')}",
            f"Hostname:             {state.get('hostname', '')}",
            f"Username:             {state.get('username', '')}",
            f"Root login:           {'Enabled' if state.get('root_password') else 'Disabled'}",
            f"Desktop environment:  {state.get('desktop_environment') or 'None / minimal'}",
            f"Language:             {state.get('locale', '')}",
            f"Keyboard layout:      {state.get('keyboard_layout', '')}",
            f"Timezone:             {state.get('timezone', '')}",
            f"Mirror region:        {state.get('mirror_region', 'Worldwide')}",
            f"Kernel:               {state.get('kernel', 'linux')}",
            f"Multilib:             {'Enabled' if state.get('enable_multilib') else 'Disabled'}",
            f"Extra packages:       {' '.join(state.get('extra_packages', [])) or '(none)'}",
            f"Internet:             {'Connected' if internet_connected else 'Not connected'}",
            f"MuliOS profile:       {state.get('profile_name', state.get('profile', 'generic'))}",
        ]

        if not internet_connected:
            lines.append(
                "\nNote: installation will use the packages already available "
                "in the MuliOS installation environment. Additional packages "
                "requiring the network may need to be installed after first boot."
            )

        self.summary_box.setPlainText("\n".join(lines))
