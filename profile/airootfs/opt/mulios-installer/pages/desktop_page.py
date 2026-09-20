from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QButtonGroup

from widgets.select_card import SelectCard
from config.settings import DESKTOP_ENVIRONMENTS


class DesktopPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Desktop environment")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        subtitle = QLabel("Choose what your MuliOS desktop looks like.")
        subtitle.setObjectName("SubtitleLabel")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._value_by_button = {}

        for i, (value, label) in enumerate(DESKTOP_ENVIRONMENTS):
            card = SelectCard("", label, object_name="SelectCard")
            row, col = divmod(i, 2)
            grid.addWidget(card, row, col)
            self.button_group.addButton(card)
            self._value_by_button[card] = value

        layout.addLayout(grid)
        layout.addStretch()

        # Default to first entry (Xfce, MuliOS default)
        first_button = list(self._value_by_button.keys())[0]
        first_button.setChecked(True)

    def selected_desktop(self):
        checked = self.button_group.checkedButton()
        if checked is None:
            return DESKTOP_ENVIRONMENTS[0][0]
        return self._value_by_button[checked]
