from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QLineEdit, QPushButton, QMessageBox, QRadioButton, QButtonGroup
)

from backend.system_info import check_internet, scan_wifi, connect_wifi


class NetworkPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Connect to the internet")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "An internet connection allows MuliOS to download additional packages during installation "
            "and lets MUpdate download your MuliOS profile after install."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Checking connection...")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        recheck_btn = QPushButton("Recheck")
        recheck_btn.setObjectName("SecondaryButton")
        recheck_btn.clicked.connect(self.recheck_connection)
        status_row.addWidget(recheck_btn)
        layout.addLayout(status_row)

        wifi_row = QHBoxLayout()
        self.wifi_list = QListWidget()
        wifi_row.addWidget(self.wifi_list, stretch=2)

        form_col = QVBoxLayout()
        self.password_field = QLineEdit()
        self.password_field.setPlaceholderText("Wi-Fi password (leave blank if open)")
        self.password_field.setEchoMode(QLineEdit.Password)
        form_col.addWidget(self.password_field)

        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self.connect_to_selected)
        form_col.addWidget(connect_btn)

        rescan_btn = QPushButton("Scan for networks")
        rescan_btn.setObjectName("SecondaryButton")
        rescan_btn.clicked.connect(self.scan)
        form_col.addWidget(rescan_btn)
        form_col.addStretch()
        wifi_row.addLayout(form_col, stretch=1)
        layout.addLayout(wifi_row)

        layout.addSpacing(6)
        network_mode_label = QLabel("Network configuration for the installed system")
        network_mode_label.setObjectName("SectionLabel")
        layout.addWidget(network_mode_label)

        self.mode_group = QButtonGroup(self)
        self.nm_radio = QRadioButton("Use NetworkManager (recommended for desktops/laptops)")
        self.copy_radio = QRadioButton("Copy this live session's network configuration")
        self.nm_radio.setChecked(True)
        self.mode_group.addButton(self.nm_radio)
        self.mode_group.addButton(self.copy_radio)
        layout.addWidget(self.nm_radio)
        layout.addWidget(self.copy_radio)

        self._is_connected = False
        self.recheck_connection()
        self.scan()

    def recheck_connection(self):
        self._is_connected = check_internet()
        if self._is_connected:
            self.status_label.setText("â— Connected to the internet")
            self.status_label.setStyleSheet("color: #319cc8; font-weight: 600;")
        else:
            self.status_label.setText("â— Not connected")
            self.status_label.setStyleSheet("color: #c0392b; font-weight: 600;")

    def is_connected(self) -> bool:
        return self._is_connected

    def scan(self):
        self.wifi_list.clear()
        networks = scan_wifi()
        if not networks:
            self.wifi_list.addItem("No Wi-Fi networks found (or nmcli unavailable).")
            return
        for net in networks:
            label = f"{net['ssid']}   ({net['signal']}%{' Â· ' + net['security'] if net['security'] else ''})"
            item = QListWidgetItem(label)
            item.setData(1000, net["ssid"])
            self.wifi_list.addItem(item)

    def connect_to_selected(self):
        item = self.wifi_list.currentItem()
        if not item or not item.data(1000):
            QMessageBox.warning(self, "No network selected", "Select a Wi-Fi network first.")
            return
        ok, message = connect_wifi(item.data(1000), self.password_field.text())
        if ok:
            QMessageBox.information(self, "Connected", f"Connected to {item.data(1000)}.")
        else:
            QMessageBox.warning(self, "Connection failed", message or "Could not connect.")
        self.recheck_connection()

    def network_mode(self) -> str:
        return "networkmanager" if self.nm_radio.isChecked() else "copy_iso"

