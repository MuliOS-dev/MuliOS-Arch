import os
import sys

from PySide6.QtCore import Qt, QRectF, QUrl, Property, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen, QFont, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QScrollArea,
    QButtonGroup,
    QStackedWidget,
)

ASSET_DIR = os.path.dirname(os.path.abspath(__file__))

ACCENT = "#0096FF"
ACCENT_HOVER = "#007ACC"

LIGHT_THEME = {
    "bg": "#ffffff",
    "fg": "#1a1a1a",
    "muted_fg": "#6b7280",
    "sidebar_bg": "#ffffff",
    "sidebar_border": "#ffffff",
    "card_bg": "#f4f5fa",
    "card_hover": "#eceeff",
    "divider": "#ececf3",
    "button_fg": "#3a3a3a",
    "button_active_bg": "#eceeff",
    "accent": ACCENT,
    "accent_hover": ACCENT_HOVER,
    "switch_off": "#9a9dab",
    "switch_off_border": "#7d808f",
}

DARK_THEME = {
    "bg": "#15161c",
    "fg": "#f2f2f5",
    "muted_fg": "#9a9aa5",
    "sidebar_bg": "#15161c",
    "sidebar_border": "#15161c",
    "card_bg": "#20212b",
    "card_hover": "#262838",
    "divider": "#2a2b35",
    "button_fg": "#d8d8e0",
    "button_active_bg": "#262838",
    "accent": ACCENT,
    "accent_hover": ACCENT_HOVER,
    "switch_off": "#565866",
    "switch_off_border": "#71727f",
}

# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------
MAIN_DEVELOPER = "Jxstaboy"
LEAD_DEVELOPERS = ["nevskydev", "redstonecoredev"]
DEVELOPERS = ["archivearther", "xren229", "quoc_baoz", "yuiop74931"]

# ---------------------------------------------------------------------------
# Support links
# ---------------------------------------------------------------------------
SUPPORT_LINKS = [
    ("github.png", "Main Repository", "https://github.com/MuliOS-dev/MuliOS-Arch"),
    ("github.png", "Organisation", "https://github.com/MuliOS-dev"),
    ("github.png", "Issues", "https://github.com/MuliOS-dev/MuliOS-Arch/issues"),
    ("discord.png", "Discord", "https://discord.gg/BUrDmvg9CW"),
]


def asset_path(name):
    return os.path.join(ASSET_DIR, "icons", name)


def load_pixmap(name, size):
    pix = QPixmap(asset_path(name))
    if pix.isNull():
        return pix
    if "discord" in name:
        return pix.scaled(int(size * 1.8), int(size * 1.8), Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


# ---------------------------------------------------------------------------
# Clickable Label
# ---------------------------------------------------------------------------
class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Animated toggle switch
# ---------------------------------------------------------------------------
class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent=None, width=44, height=22):
        super().__init__(parent)
        self._w = width
        self._h = height
        self.setFixedSize(width, height)
        self.setCursor(Qt.PointingHandCursor)

        self._checked = False
        self._pos = 0.0

        self._on = QColor(ACCENT)
        self._on_border = QColor(ACCENT_HOVER)
        self._off = QColor("#9a9dab")
        self._off_border = QColor("#7d808f")
        self._knob = QColor("#ffffff")

        self._anim = QPropertyAnimation(self, b"knobPos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

    def getKnobPos(self):
        return self._pos

    def setKnobPos(self, value):
        self._pos = value
        self.update()

    knobPos = Property(float, getKnobPos, setKnobPos)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked, animate=True, emit=True):
        checked = bool(checked)
        if self._checked == checked:
            return
        self._checked = checked
        target = 1.0 if checked else 0.0
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self.setKnobPos(target)
        if emit:
            self.toggled.emit(checked)

    def set_colors(self, on, on_border, off, off_border, knob="#ffffff"):
        self._on = QColor(on)
        self._on_border = QColor(on_border)
        self._off = QColor(off)
        self._off_border = QColor(off_border)
        self._knob = QColor(knob)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)

    @staticmethod
    def _lerp(c1, c2, t):
        r = c1.red() + (c2.red() - c1.red()) * t
        g = c1.green() + (c2.green() - c1.green()) * t
        b = c1.blue() + (c2.blue() - c1.blue()) * t
        return QColor(int(r), int(g), int(b))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        t = self._pos
        track_color = self._lerp(self._off, self._on, t)
        border_color = self._lerp(self._off_border, self._on_border, t)
        r = self._h / 2.0

        track_rect = QRectF(0.5, 0.5, self._w - 1, self._h - 1)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(track_rect, r, r)

        knob_d = self._h - 4
        knob_x = 2 + t * (self._w - self._h)
        knob_rect = QRectF(knob_x, 2, knob_d, knob_d)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(QBrush(self._knob))
        painter.drawEllipse(knob_rect)


# ---------------------------------------------------------------------------
# Clickable card frame
# ---------------------------------------------------------------------------
class ClickableCard(QFrame):
    def __init__(self, url, parent=None):
        super().__init__(parent)
        self._url = url
        self.setObjectName("linkCard")
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            QDesktopServices.openUrl(QUrl(self._url))
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MuliOS Credits and Support")
        self.setFixedSize(1325, 765)

        self.theme = DARK_THEME
        self.chips = []
        self.section_titles = []
        self.link_cards = []

        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())

        self.divider = QFrame()
        self.divider.setObjectName("divider")
        self.divider.setFixedWidth(1)
        root_layout.addWidget(self.divider)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_credits_page())
        self.stack.addWidget(self._build_support_page())
        root_layout.addWidget(self.stack, 1)

        self.credits_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.support_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.credits_btn.clicked.connect(self._refresh_nav_style)
        self.support_btn.clicked.connect(self._refresh_nav_style)

        self.theme_switch.toggled.connect(self._on_theme_toggled)
        self.theme_caption.clicked.connect(
            lambda: self.theme_switch.setChecked(not self.theme_switch.isChecked())
        )

        self.theme_switch.setChecked(True, animate=False, emit=False)
        self.apply_theme(DARK_THEME)
        self._center_on_screen()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.y() + (screen.height() - self.height()) // 2
        self.move(x, y)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand_row = QWidget()
        brand_layout = QHBoxLayout(brand_row)
        brand_layout.setContentsMargins(18, 22, 18, 18)
        self.brand_label = QLabel("MuliOS")
        self.brand_label.setObjectName("brand")
        brand_layout.addWidget(self.brand_label)
        brand_layout.addStretch()
        layout.addWidget(brand_row)

        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(12, 0, 12, 0)
        nav_layout.setSpacing(4)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        self.credits_btn = QPushButton("Credits")
        self.support_btn = QPushButton("Support")
        for i, btn in enumerate([self.credits_btn, self.support_btn]):
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(40)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.nav_group.addButton(btn, i)
            nav_layout.addWidget(btn)
        self.credits_btn.setChecked(True)

        layout.addWidget(nav_widget)
        layout.addStretch(1)

        theme_row = QWidget()
        theme_layout = QHBoxLayout(theme_row)
        theme_layout.setContentsMargins(14, 6, 14, 18)
        self.theme_caption = ClickableLabel("Dark mode")
        self.theme_caption.setObjectName("themeCaption")
        self.theme_caption.setCursor(Qt.PointingHandCursor)
        self.theme_switch = ToggleSwitch()
        theme_layout.addWidget(self.theme_caption)
        theme_layout.addStretch()
        theme_layout.addWidget(self.theme_switch)
        layout.addWidget(theme_row)

        return sidebar

    def _refresh_nav_style(self):
        for btn in (self.credits_btn, self.support_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _make_section_title(self, text):
        lbl = QLabel(text.upper())
        lbl.setObjectName("sectionTitle")
        lbl.setAlignment(Qt.AlignCenter)
        self.section_titles.append(lbl)
        return lbl

    def _make_chip(self, text):
        chip = QLabel(text)
        chip.setObjectName("chip")
        chip.setAlignment(Qt.AlignCenter)
        self.chips.append(chip)
        return chip

    def _make_row(self, names):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setSpacing(10)
        row_layout.setContentsMargins(0, 0, 0, 0)
        for name in names:
            row_layout.addWidget(self._make_chip(name))
        return row

    def _build_credits_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("creditsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content.setObjectName("creditsContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(60, 48, 60, 40)
        layout.setSpacing(0)

        self.logo_label = QLabel()
        self.logo_label.setPixmap(load_pixmap("logo.png", 120))
        self.logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.logo_label)

        self.credits_title = QLabel("MuliOS Credits")
        self.credits_title.setObjectName("pageTitle")
        self.credits_title.setAlignment(Qt.AlignCenter)
        layout.addSpacing(18)
        layout.addWidget(self.credits_title)

        self.credits_subtitle = QLabel("Thanks to everyone who helped bring MuliOS to life.")
        self.credits_subtitle.setObjectName("subtitle")
        self.credits_subtitle.setAlignment(Qt.AlignCenter)
        layout.addSpacing(6)
        layout.addWidget(self.credits_subtitle)

        self.credits_sep = QFrame()
        self.credits_sep.setObjectName("hDivider")
        self.credits_sep.setFixedHeight(1)
        layout.addSpacing(30)
        layout.addWidget(self.credits_sep)

        layout.addSpacing(26)
        layout.addWidget(self._make_section_title("Main Developer"))
        layout.addSpacing(14)
        layout.addWidget(self._make_chip(MAIN_DEVELOPER), alignment=Qt.AlignCenter)

        layout.addSpacing(30)
        layout.addWidget(self._make_section_title("Lead Developers"))
        layout.addSpacing(14)
        layout.addWidget(self._make_row(LEAD_DEVELOPERS), alignment=Qt.AlignCenter)

        layout.addSpacing(30)
        layout.addWidget(self._make_section_title("Developers"))
        layout.addSpacing(14)
        layout.addWidget(self._make_row(DEVELOPERS), alignment=Qt.AlignCenter)

        layout.addSpacing(40)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        return page

    def _build_link_card(self, icon_name, title, url):
        card = ClickableCard(url)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(18, 14, 18, 14)

        icon_label = QLabel()
        icon_label.setObjectName("cardIcon")
        icon_label.setFixedSize(36, 36)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setPixmap(load_pixmap(icon_name, 28))
        card_layout.addWidget(icon_label)

        text_col = QWidget()
        text_col.setObjectName("cardText")
        text_layout = QVBoxLayout(text_col)
        text_layout.setContentsMargins(16, 0, 0, 0)
        text_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        url_label = QLabel(url)
        url_label.setObjectName("linkText")
        text_layout.addWidget(title_label)
        text_layout.addWidget(url_label)
        card_layout.addWidget(text_col, 1)

        self.link_cards.append(card)
        return card

    def _build_support_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setAlignment(Qt.AlignCenter)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setAlignment(Qt.AlignCenter)
        inner_layout.setSpacing(0)
        inner.setFixedWidth(600)

        question = QLabel("Need help or support?")
        question.setObjectName("pageTitle")
        question.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(question)

        message = QLabel("Reach out through any of the channels below, we're happy to help.")
        message.setObjectName("subtitle")
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        inner_layout.addSpacing(6)
        inner_layout.addWidget(message)
        inner_layout.addSpacing(30)

        for i, (icon_name, title, url) in enumerate(SUPPORT_LINKS):
            if i > 0:
                inner_layout.addSpacing(10)
            inner_layout.addWidget(self._build_link_card(icon_name, title, url))

        page_layout.addWidget(inner)
        return page

    def _on_theme_toggled(self, is_dark):
        self.apply_theme(DARK_THEME if is_dark else LIGHT_THEME)

    def apply_theme(self, theme):
        self.theme = theme
        self.theme_caption.setText("Dark mode")
        qss = f"""
        QMainWindow, QWidget {{
            background: {theme['bg']};
            color: {theme['fg']};
        }}
        QFrame#sidebar {{
            background: {theme['sidebar_bg']};
        }}
        QFrame#divider {{
            background: {theme['sidebar_border']};
            border: none;
        }}
        QFrame#hDivider {{
            background: {theme['divider']};
            border: none;
        }}
        QLabel#brand {{
            color: {theme['accent']};
            font-size: 14px;
            font-weight: 700;
            background: transparent;
        }}
        QPushButton#navButton {{
            text-align: left;
            padding: 0px 16px;
            border: none;
            border-radius: 8px;
            background: transparent;
            color: {theme['button_fg']};
            font-size: 13px;
        }}
        QPushButton#navButton:hover {{
            background: {theme['card_hover']};
        }}
        QPushButton#navButton:checked {{
            background: {theme['button_active_bg']};
            color: {theme['accent']};
            font-weight: 700;
        }}
        QLabel#themeCaption {{
            background: transparent;
            color: {theme['button_fg']};
            font-size: 13px;
        }}
        QLabel#pageTitle {{
            background: transparent;
            color: {theme['fg']};
            font-size: 24px;
            font-weight: 700;
        }}
        QLabel#subtitle {{
            background: transparent;
            color: {theme['muted_fg']};
            font-size: 13px;
        }}
        QLabel#sectionTitle {{
            background: transparent;
            color: {theme['accent']};
            font-size: 12px;
            font-weight: 700;
        }}
        QLabel#chip {{
            background: {theme['card_bg']};
            color: {theme['fg']};
            border-radius: 8px;
            padding: 9px 22px;
            font-size: 13px;
        }}
        QFrame#linkCard {{
            background: {theme['card_bg']};
            border-radius: 10px;
        }}
        QFrame#linkCard:hover {{
            background: {theme['card_hover']};
        }}
        QWidget#cardText {{
            background: transparent;
        }}
        QLabel#cardIcon {{
            background: transparent;
        }}
        QLabel#cardTitle {{
            background: transparent;
            color: {theme['fg']};
            font-size: 13px;
            font-weight: 700;
        }}
        QLabel#linkText {{
            background: transparent;
            color: {theme['accent']};
            font-size: 11px;
        }}
        QScrollArea#creditsScroll, QWidget#creditsContent {{
            background: {theme['bg']};
            border: none;
        }}
        """
        self.setStyleSheet(qss)
        self.theme_switch.set_colors(
            on=theme["accent"],
            on_border=theme["accent_hover"],
            off=theme["switch_off"],
            off_border=theme["switch_off_border"],
        )
        self._refresh_nav_style()


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()