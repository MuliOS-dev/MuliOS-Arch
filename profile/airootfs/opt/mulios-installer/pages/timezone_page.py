from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from backend.system_info import list_timezones
from widgets.searchable_picker import SearchablePicker


class TimezonePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Select your timezone")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel("Used to set the system clock correctly.")
        subtitle.setObjectName("SubtitleLabel")
        layout.addWidget(subtitle)

        self.picker = SearchablePicker(list_timezones(), default="UTC")
        layout.addWidget(self.picker, stretch=1)

    def selected_timezone(self) -> str:
        return self.picker.selected() or "UTC"
