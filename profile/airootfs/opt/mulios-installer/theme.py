"""Visual theme for the native MuliOS installer."""

PRIMARY = "#319cc8"
BG_DARKEST = "rgba(13, 16, 21, 205)"
BG_DARK = "rgba(20, 23, 29, 185)"
BG_PANEL = "rgba(36, 40, 48, 205)"
BORDER = "rgba(255, 255, 255, 32)"
TEXT_PRIMARY = "#f2f3f5"
TEXT_SECONDARY = "#a7abb3"
TEXT_DISABLED = "#5c6066"
RADIUS = "12px"


def stylesheet() -> str:
    return f"""
    QWidget {{
        background: transparent;
        color: {TEXT_PRIMARY};
        font-family: "Inter", "Ubuntu", "Cantarell", sans-serif;
        font-size: 10.5pt;
    }}

    #Sidebar {{
        background-color: {BG_DARKEST};
        border: 1px solid {BORDER};
        border-radius: {RADIUS};
    }}
    #Sidebar QLabel {{
        color: {TEXT_SECONDARY};
        background: transparent;
    }}
    #Sidebar QLabel[stepActive="true"] {{
        color: {PRIMARY};
        font-weight: 600;
    }}
    #Sidebar QLabel[stepDone="true"] {{
        color: {TEXT_PRIMARY};
    }}

    #ContentPanel {{
        background-color: {BG_DARK};
        border: 1px solid {BORDER};
        border-radius: {RADIUS};
    }}
    #NavBar {{
        background-color: rgba(20, 23, 29, 180);
        border-top: 1px solid {BORDER};
        border-bottom-left-radius: {RADIUS};
        border-bottom-right-radius: {RADIUS};
    }}

    QLabel#TitleLabel {{
        font-size: 19pt;
        font-weight: 600;
        color: {TEXT_PRIMARY};
        background: transparent;
    }}
    QLabel#SubtitleLabel {{
        font-size: 10.5pt;
        color: {TEXT_SECONDARY};
        background: transparent;
    }}
    QLabel#SectionLabel {{
        font-size: 10.5pt;
        font-weight: 600;
        color: {TEXT_PRIMARY};
        background: transparent;
    }}
    QLabel#FixedChoiceCard {{
        background: {BG_PANEL};
        border: 1px solid {BORDER};
        border-radius: {RADIUS};
        padding: 18px;
        font-size: 12pt;
        font-weight: 600;
    }}
    QLabel[warning="true"] {{
        color: #e7c46a;
    }}
    QLabel[error="true"] {{
        color: #e06666;
    }}

    QPushButton {{
        background-color: {BG_PANEL};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 9px;
        padding: 8px 18px;
    }}
    QPushButton:hover {{
        border: 1px solid {PRIMARY};
        background-color: rgba(55, 61, 72, 220);
    }}
    QPushButton#PrimaryButton {{
        background-color: {PRIMARY};
        border: none;
        color: #08131a;
        font-weight: 600;
    }}
    QPushButton#PrimaryButton:hover {{
        background-color: #4bb0d6;
    }}
    QPushButton#PrimaryButton:pressed {{
        background-color: #257b9e;
        color: {TEXT_PRIMARY};
    }}
    QPushButton#PrimaryButton:disabled {{
        background-color: #35424a;
        color: {TEXT_DISABLED};
    }}
    QPushButton#SecondaryButton {{
        background-color: rgba(25, 28, 34, 160);
    }}

    QLineEdit, QComboBox, QListWidget, QTextEdit, QSpinBox {{
        background-color: rgba(28, 32, 39, 220);
        border: 1px solid {BORDER};
        border-radius: 9px;
        padding: 7px;
        selection-background-color: {PRIMARY};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border: 1px solid {PRIMARY};
    }}
    QComboBox::drop-down {{
        border: none;
    }}

    QProgressBar {{
        border: 1px solid {BORDER};
        border-radius: 8px;
        text-align: center;
        background-color: rgba(24, 27, 33, 210);
        min-height: 12px;
    }}
    QProgressBar::chunk {{
        background-color: {PRIMARY};
        border-radius: 7px;
    }}

    QRadioButton, QCheckBox {{
        spacing: 8px;
    }}
    QRadioButton::indicator, QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {BORDER};
        border-radius: 4px;
        background-color: rgba(28, 32, 39, 220);
    }}
    QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
        background-color: {PRIMARY};
        border: 1px solid {PRIMARY};
    }}

    QPushButton#ProfileCard, QPushButton#SelectCard {{
        background-color: {BG_PANEL};
        border: 1px solid {BORDER};
        border-radius: 10px;
        text-align: left;
        padding: 0px;
    }}
    QPushButton#ProfileCard:hover, QPushButton#SelectCard:hover {{
        border: 1px solid {PRIMARY};
    }}
    QPushButton#ProfileCard:checked, QPushButton#SelectCard:checked {{
        border: 1px solid {PRIMARY};
        background-color: rgba(36, 51, 58, 225);
    }}
    QLabel#ProfileCardIcon, QLabel#ProfileCardTitle, QLabel#ProfileCardDescription {{
        background: transparent;
    }}
    QLabel#ProfileCardTitle {{
        font-size: 11.5pt;
        font-weight: 700;
    }}
    QLabel#ProfileCardDescription {{
        font-size: 9pt;
        color: {TEXT_SECONDARY};
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(255,255,255,45);
        border-radius: 5px;
        min-height: 24px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """
