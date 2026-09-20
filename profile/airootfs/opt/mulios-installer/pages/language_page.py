from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from backend.system_info import list_locales
from widgets.searchable_picker import SearchablePicker


class LanguagePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Select your language")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel("This sets the system locale used after install.")
        subtitle.setObjectName("SubtitleLabel")
        layout.addWidget(subtitle)

        self.picker = SearchablePicker(list_locales(), default="en_US.UTF-8")
        layout.addWidget(self.picker, stretch=1)

    def selected_locale(self) -> str:
        return self.picker.selected() or "en_US.UTF-8"
