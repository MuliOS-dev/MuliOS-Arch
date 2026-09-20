"""
widgets/searchable_picker.py

A filter box + list widget used by any page that needs to pick one item
out of a long list (locales, keyboard layouts, timezones, mirror
regions, ...). Typing narrows the list; nothing is auto-selected.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QListWidget
from PySide6.QtCore import Qt

class SearchablePicker(QWidget):
    def __init__(self, items: list[str], default: str | None = None, parent=None):
        super().__init__(parent)
        self._all_items = items

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText("Type to filter...")
        self.filter_box.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter_box)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self._apply_filter("")
        if default and default in items:
            matches = self.list_widget.findItems(default, Qt.MatchContains)
            for item in matches:
                if item.text() == default:
                    self.list_widget.setCurrentItem(item)
                    break

    def _apply_filter(self, text: str):
        self.list_widget.clear()
        text = text.strip().lower()
        for item in self._all_items:
            if text in item.lower():
                self.list_widget.addItem(item)
        if self.list_widget.count() > 0 and not text:
            self.list_widget.setCurrentRow(0)

    def selected(self) -> str | None:
        item = self.list_widget.currentItem()
        return item.text() if item else None
