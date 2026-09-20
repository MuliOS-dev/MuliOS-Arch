"""
widgets/toggle_switch.py

A small iOS-style toggle switch (rounded track + sliding circle handle),
since PySide6 has no built-in switch widget.
"""

from PySide6.QtWidgets import QAbstractButton, QSizePolicy
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, Property, QRectF
from PySide6.QtGui import QPainter, QColor

from theme import PRIMARY


class ToggleSwitch(QAbstractButton):
    def __init__(self, checked=False, on_color=PRIMARY, off_color="#4a4e56", parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self._on_color = QColor(on_color)
        self._off_color = QColor(off_color)
        self._handle_color = QColor("#ffffff")

        self._offset = 1.0 if checked else 0.0

        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

        self.toggled.connect(self._animate_to_state)

    def sizeHint(self):
        return QSize(46, 26)

    def _animate_to_state(self, checked: bool):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def getOffset(self):
        return self._offset

    def setOffset(self, value):
        self._offset = value
        self.update()

    offset = Property(float, getOffset, setOffset)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        track_rect = QRectF(0, 0, self.width(), self.height())
        radius = track_rect.height() / 2

        track_color = self._blend(self._off_color, self._on_color, self._offset)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, radius, radius)

        handle_diameter = track_rect.height() - 4
        travel = track_rect.width() - handle_diameter - 4
        handle_x = 2 + travel * self._offset
        handle_rect = QRectF(handle_x, 2, handle_diameter, handle_diameter)

        painter.setBrush(self._handle_color)
        painter.drawEllipse(handle_rect)

    @staticmethod
    def _blend(color_a: QColor, color_b: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, t))
        r = color_a.red() + (color_b.red() - color_a.red()) * t
        g = color_a.green() + (color_b.green() - color_a.green()) * t
        b = color_a.blue() + (color_b.blue() - color_a.blue()) * t
        return QColor(int(r), int(g), int(b))
