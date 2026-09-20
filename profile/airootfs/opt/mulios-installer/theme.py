"""
theme.py - MuliOS Arch installer visual theme.

Per spec: dark gray, minimalistic, MuliOS/Windows 11 Setup/Fedora
Installer quality. Accent colors used ONLY for primary actions,
progress, selection highlights, and icons - never as general decoration.
"""

PRIMARY = "#319cc8"     # Continue/Install buttons, progress, selection
SECONDARY = "#1748a0"   # pressed states, secondary accents, links

BG_DARKEST = "#1b1d21"     # sidebar
BG_DARK = "#232529"        # main window background
BG_PANEL = "#2a2d32"       # cards, inputs
BORDER = "#3a3d43"

TEXT_PRIMARY = "#f2f3f5"
TEXT_SECONDARY = "#a7abb3"
TEXT_DISABLED = "#5c6066"

RADIUS = "8px"


def stylesheet() -> str:
    return f"""
    QWidget {{
        background-color: {BG_DARK};
        color: {TEXT_PRIMARY};
        font-family: "Inter", "Ubuntu", "Cantarell", sans-serif;
        font-size: 10.5pt;
    }}

    #Sidebar {{
        background-color: {BG_DARKEST};
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
    }}
    #NavBar {{
        background-color: {BG_DARK};
        border-top: 1px solid {BORDER};
    }}

    QLabel#TitleLabel {{
        font-size: 19pt;
        font-weight: 600;
        color: {TEXT_PRIMARY};
    }}
    QLabel#SubtitleLabel {{
        font-size: 10.5pt;
        color: {TEXT_SECONDARY};
    }}
    QLabel#SectionLabel {{
        font-size: 10.5pt;
        font-weight: 600;
        color: {TEXT_PRIMARY};
    }}

    QPushButton {{
        background-color: {BG_PANEL};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: {RADIUS};
        padding: 8px 18px;
    }}
    QPushButton:hover {{
        border: 1px solid {PRIMARY};
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
        background-color: {SECONDARY};
        color: {TEXT_PRIMARY};
    }}
    QPushButton#PrimaryButton:disabled {{
        background-color: #35424a;
        color: {TEXT_DISABLED};
    }}
    QPushButton#SecondaryButton {{
        background-color: transparent;
    }}
    QPushButton#SecondaryButton:hover {{
        background-color: #33363c;
    }}

    QLineEdit, QComboBox, QListWidget, QTextEdit, QSpinBox {{
        background-color: {BG_PANEL};
        border: 1px solid {BORDER};
        border-radius: {RADIUS};
        padding: 6px;
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
        border-radius: {RADIUS};
        text-align: center;
        background-color: {BG_PANEL};
    }}
    QProgressBar::chunk {{
        background-color: {PRIMARY};
        border-radius: {RADIUS};
    }}

    QRadioButton, QCheckBox {{
        spacing: 8px;
    }}
    QRadioButton::indicator, QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {BORDER};
        border-radius: 4px;
        background-color: {BG_PANEL};
    }}
    QRadioButton::indicator:checked, QCheckBox::indicator:checked {{
        background-color: {PRIMARY};
        border: 1px solid {PRIMARY};
    }}

    QPushButton#ProfileCard, QPushButton#SelectCard {{
        background-color: {BG_PANEL};
        border: 2px solid {BORDER};
        border-radius: 10px;
        text-align: left;
        padding: 0px;
        font-weight: normal;
    }}
    QPushButton#ProfileCard:hover, QPushButton#SelectCard:hover {{
        border: 2px solid {PRIMARY};
    }}
    QPushButton#ProfileCard:checked, QPushButton#SelectCard:checked {{
        border: 2px solid {PRIMARY};
        background-color: #24333a;
    }}
    QLabel#ProfileCardIcon {{
        font-size: 20pt;
        background: transparent;
    }}
    QLabel#ProfileCardTitle {{
        font-size: 11.5pt;
        font-weight: 700;
        color: {TEXT_PRIMARY};
        background: transparent;
    }}
    QLabel#ProfileCardDescription {{
        font-size: 9pt;
        color: {TEXT_SECONDARY};
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        border-radius: 5px;
        min-height: 24px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """

