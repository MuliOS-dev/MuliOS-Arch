from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
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
            "The selected disk will be completely erased and used "
            "entirely for MuliOS. Make sure you select the correct disk."
        )
        subtitle.setObjectName("SubtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        warning = QLabel(
            "WARNING: Installing MuliOS will destroy all data on the "
            "selected disk."
        )
        warning.setObjectName("WarningLabel")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        self.disk_list = QListWidget()
        self.disk_list.setSelectionMode(
            QListWidget.SingleSelection
        )
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
            self.disk_list.addItem(
                "No disks detected - is this running as root?"
            )
            return

        for disk in disks:
            path = disk["path"]
            size = disk.get("size", "?")
            model = disk.get("model", "Unknown")
            transport = disk.get("transport", "")
            removable = disk.get("removable", False)
            mountpoints = disk.get("mountpoints", [])

            details = [
                path,
                size,
                model,
            ]

            if transport:
                details.append(transport)

            if removable:
                details.append("REMOVABLE")

            if mountpoints:
                details.append(
                    "MOUNTED: " +
                    ", ".join(mountpoints)
                )

            label = "   -   ".join(details)

            item = QListWidgetItem(label)
            item.setData(1000, path)

            if mountpoints:
                item.setToolTip(
                    "This disk currently has mounted filesystems "
                    "and cannot safely be used until they are unmounted."
                )

            self.disk_list.addItem(item)

        # Do not automatically select a destructive target.
        self.disk_list.clearSelection()
        self.disk_list.setCurrentItem(None)

    def selected_disk(self):
        item = self.disk_list.currentItem()

        if item is None:
            return None

        return item.data(1000)
