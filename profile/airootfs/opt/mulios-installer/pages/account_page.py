from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QLabel,
)

from utils.validators import validate_hostname, validate_username, validate_password


class AccountPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Account setup")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.hostname = QLineEdit()
        self.hostname.setPlaceholderText("muli-pc")
        form.addRow("Computer name", self.hostname)

        self.root_password = QLineEdit()
        self.root_password.setEchoMode(QLineEdit.Password)
        self.root_password.setPlaceholderText(
            "Leave blank to disable root login (recommended)"
        )
        form.addRow("Root password", self.root_password)

        self.username = QLineEdit()
        self.username.setPlaceholderText("jane")
        form.addRow("Username", self.username)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        form.addRow("Password", self.password)

        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.Password)
        form.addRow("Confirm password", self.confirm_password)

        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        layout.addStretch()

    def _set_message(self, text: str, *, error: bool = False):
        self.error_label.setText(text)
        self.error_label.setProperty("warning", not error)
        self.error_label.setProperty("error", error)
        self.error_label.style().unpolish(self.error_label)
        self.error_label.style().polish(self.error_label)

    def validate(self) -> bool:
        ok, msg = validate_hostname(self.hostname.text())
        if not ok:
            self._set_message(msg, error=True)
            return False

        ok, msg = validate_username(self.username.text())
        if not ok:
            self._set_message(msg, error=True)
            return False

        ok, msg = validate_password(
            self.password.text(),
            self.confirm_password.text(),
        )
        if not ok:
            self._set_message(msg, error=True)
            return False

        self._set_message(msg, error=False)
        return True

    def data(self) -> dict:
        return {
            "hostname": self.hostname.text().strip(),
            "root_password": self.root_password.text(),
            "username": self.username.text().strip(),
            "user_password": self.password.text(),
        }
