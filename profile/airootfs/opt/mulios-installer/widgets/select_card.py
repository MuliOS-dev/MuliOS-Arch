"""
widgets/select_card.py

A checkable "card" button showing an icon, title, and short description.
Used for the MuliOS profile picker (object name "ProfileCard") and for
other single-choice grids like desktop environment selection (object
name "SelectCard") - both are styled identically in theme.py.
"""

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt


class SelectCard(QPushButton):
    def __init__(self, icon: str, title: str, description: str = "", object_name="SelectCard", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setObjectName(object_name)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(100 if description else 70)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        if icon:
            icon_label = QLabel(icon)
            icon_label.setObjectName("ProfileCardIcon")
            layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setObjectName("ProfileCardTitle")
        layout.addWidget(title_label)

        widgets_to_passthrough = [title_label]
        if icon:
            widgets_to_passthrough.append(icon_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setObjectName("ProfileCardDescription")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
            widgets_to_passthrough.append(desc_label)

        layout.addStretch()

        # Let child labels ignore clicks so they don't block toggling the button
        for w in widgets_to_passthrough:
            w.setAttribute(Qt.WA_TransparentForMouseEvents)


# Backwards-compatible alias, since the MuliOS profile picker was originally
# built against a "ProfileCard" class name.
class ProfileCard(SelectCard):
    def __init__(self, icon: str, title: str, description: str, parent=None):
        super().__init__(icon, title, description, object_name="ProfileCard", parent=parent)
