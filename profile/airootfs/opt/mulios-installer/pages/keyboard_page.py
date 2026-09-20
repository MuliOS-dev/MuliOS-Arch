from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from backend.system_info import list_keyboard_layouts
from widgets.searchable_picker import SearchablePicker


class KeyboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Select your keyboard layout")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel("Used for the console and, by default, the desktop too.")
        subtitle.setObjectName("SubtitleLabel")
        layout.addWidget(subtitle)

        self.picker = SearchablePicker(list_keyboard_layouts(), default="us")
        layout.addWidget(self.picker, stretch=1)

    def selected_layout(self) -> str:
        return self.picker.selected() or "us"
