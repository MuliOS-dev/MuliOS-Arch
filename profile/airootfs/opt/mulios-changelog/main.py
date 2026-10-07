#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from steps import STEPS

BASE_DIR = Path(__file__).resolve().parent


class ChangelogWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_step = 0
        self.steps = STEPS
        self.image_animation = None

        self.setWindowTitle("MuliOS")
        self.resize(1100, 700)
        self.setMinimumSize(850, 550)

        self.setStyleSheet("""
            QMainWindow {
                background: white;
            }

            QWidget {
                background: white;
                color: #111111;
            }

            QLabel#Title {
                font-size: 32px;
                font-weight: 600;
                color: #111111;
            }

            QLabel#Description {
                font-size: 16px;
                color: #666666;
            }

            QPushButton {
                background: #111111;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 11px 22px;
                font-size: 14px;
            }

            QPushButton:hover {
                background: #2b2b2b;
            }

            QPushButton:disabled {
                background: #dddddd;
                color: #888888;
            }
        """)

        self.build_ui()
        self.show_step(0)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(360)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(50, 50, 40, 40)
        sidebar_layout.setSpacing(18)

        self.step_label = QLabel()

        self.step_label.setStyleSheet("""
            color: #888888;
            font-size: 13px;
            font-weight: 500;
        """)

        self.title_label = QLabel()
        self.title_label.setObjectName("Title")
        self.title_label.setWordWrap(True)

        self.description_label = QLabel()
        self.description_label.setObjectName("Description")
        self.description_label.setWordWrap(True)

        sidebar_layout.addWidget(self.step_label)
        sidebar_layout.addWidget(self.title_label)
        sidebar_layout.addWidget(self.description_label)
        sidebar_layout.addStretch()

        buttons = QHBoxLayout()
        buttons.setSpacing(10)

        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.previous_step)

        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_step)

        buttons.addWidget(self.back_button)
        buttons.addWidget(self.next_button)

        sidebar_layout.addLayout(buttons)

        self.image_area = QWidget()
        self.image_area.setStyleSheet("background: #f2f2f2;")

        image_layout = QVBoxLayout(self.image_area)
        image_layout.setContentsMargins(30, 30, 30, 30)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)

        image_layout.addWidget(self.image_label)

        layout.addWidget(sidebar)
        layout.addWidget(self.image_area, 1)

    def show_step(self, index):
        self.current_step = index
        step = self.steps[index]

        self.step_label.setText(
            f"{index + 1} / {len(self.steps)}"
        )

        self.title_label.setText(step["title"])
        self.description_label.setText(step["description"])

        image_path = BASE_DIR / "steps" / step["image"]

        if image_path.exists():
            pixmap = QPixmap(str(image_path))

            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.image_label.setPixmap(scaled)
        else:
            self.image_label.clear()

        self.back_button.setEnabled(index > 0)
        self.next_button.setText(
            "Finish" if index == len(self.steps) - 1 else "Next"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if not self.steps:
            return

        image_path = BASE_DIR / self.steps[self.current_step]["image"]

        if image_path.exists():
            pixmap = QPixmap(str(image_path))

            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.image_label.setPixmap(scaled)

    def fade_image(self):
        animation = QPropertyAnimation(
            self.image_label,
            b"windowOpacity",
        )

        animation.setDuration(250)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.InOutQuad)

        self.image_animation = animation
        animation.start()

    def next_step(self):
        if self.current_step >= len(self.steps) - 1:
            self.finish()
            return

        self.current_step += 1
        self.show_step(self.current_step)

        self.image_label.setWindowOpacity(0.0)
        self.fade_image()

    def previous_step(self):
        if self.current_step <= 0:
            return

        self.current_step -= 1
        self.show_step(self.current_step)

        self.image_label.setWindowOpacity(0.0)
        self.fade_image()

    def finish(self):
        self.close()

    def closeEvent(self, event):
        cleanup_script = """
sleep 1
rm -rf /opt/mulios-changelog
rm -f /usr/share/applications/mulios-changelog.desktop
rm -f /home/liveuser/Desktop/mulios-welcome.desktop
rm -f /etc/xdg/autostart/mulios-welcome.desktop
"""

        subprocess.Popen(
            ["sudo", "bash", "-c", cleanup_script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        event.accept()


def main():
    app = QApplication(sys.argv)

    window = ChangelogWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
