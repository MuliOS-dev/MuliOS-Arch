from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton
)

from backend.system_info import list_disks


class DiskPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Select installation disk")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "The selected disk will be completely erased and used entirely for MuliOS."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.disk_list = QListWidget()
        layout.addWidget(self.disk_list, stretch=1)

        refresh_row = QHBoxLayout()
        refresh_btn = QPushButton("Rescan disks")
        refresh_btn.setObjectName("SecondaryButton")
        refresh_btn.clicked.connect(self.refresh_disks)
        refresh_row.addWidget(refresh_btn)
        refresh_row.addStretch()
        layout.addLayout(refresh_row)

        self.refresh_disks()

    def refresh_disks(self):
        self.disk_list.clear()
        disks = list_disks()
        if not disks:
            self.disk_list.addItem("No disks detected - is this running as root?")
            return
        for d in disks:
            label = f"{d['path']}   -   {d.get('size', '?')}   -   {d.get('model', 'Unknown')}"
            item = QListWidgetItem(label)
            item.setData(1000, d["path"])
            self.disk_list.addItem(item)
        self.disk_list.setCurrentRow(0)

    def selected_disk(self):
        item = self.disk_list.currentItem()
        return item.data(1000) if item else None




