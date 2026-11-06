"""One warm palette for the Main Window, shared with the Chat Box and Speech Balloon."""

CREAM = "#fbf6f0"
PANEL = "#ffffff"
BORDER = "#e6d8cb"
INK = "#3b2f2f"
DIM = "#8a7a6e"
ACCENT = "#c8744a"
ACCENT_HOVER = "#b5643b"
ACCENT_SOFT = "#f6e3d6"
OBSERVED = "#b8860b"
OBSERVED_SOFT = "#fbf0d0"
DANGER = "#b24a3b"

STYLE = f"""
QMainWindow, QWidget#root, QWidget#page {{ background: {CREAM}; }}
QWidget {{ color: {INK}; font-size: 14px; }}
QLabel#title {{ font-size: 20px; font-weight: 600; }}
QLabel#hint, QLabel#note {{ color: {DIM}; font-size: 12px; }}
QLabel#note {{ color: {OBSERVED}; }}

/* sidebar */
QWidget#sidebar {{ background: {PANEL}; border-right: 1px solid {BORDER}; }}
QLabel#brand {{ font-size: 18px; font-weight: 700; color: {ACCENT}; padding: 4px 8px 12px 8px; }}
QPushButton#nav {{
    text-align: left; padding: 9px 12px; border: none; border-radius: 10px; background: transparent;
}}
QPushButton#nav:hover {{ background: {CREAM}; }}
QPushButton#nav:checked {{ background: {ACCENT_SOFT}; color: {ACCENT_HOVER}; font-weight: 600; }}
QPushButton#nav:disabled {{ color: {DIM}; }}

/* inputs */
QLineEdit, QPlainTextEdit {{
    background: {PANEL}; border: 1.5px solid {BORDER}; border-radius: 12px; padding: 8px 12px;
    selection-background-color: {ACCENT_SOFT}; selection-color: {INK};
}}
QLineEdit:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit:read-only {{ background: {CREAM}; color: {DIM}; }}

/* buttons */
QPushButton {{
    background: {PANEL}; border: 1.5px solid {BORDER}; border-radius: 10px; padding: 7px 14px;
}}
QPushButton:hover {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: {DIM}; background: {CREAM}; }}
QPushButton#primary {{ background: {ACCENT}; border-color: {ACCENT}; color: white; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#primary:disabled {{ background: {BORDER}; border-color: {BORDER}; color: white; }}
QPushButton#danger {{ color: {DANGER}; }}
QPushButton#chip {{ padding: 4px 12px; border-radius: 12px; font-size: 12px; }}
QPushButton#chip:checked {{ background: {ACCENT_SOFT}; border-color: {ACCENT}; color: {ACCENT_HOVER}; }}
QPushButton#icon {{ padding: 7px 10px; }}

/* lists and logs */
QTextBrowser {{ background: transparent; border: none; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{
    background: {PANEL}; border: 1.5px solid {BORDER}; border-radius: 12px; padding: 10px 12px; margin: 0 0 8px 0;
}}
QListWidget::item:hover {{ border-color: {ACCENT}; }}
QListWidget::item:selected {{ background: {ACCENT_SOFT}; border-color: {ACCENT}; color: {INK}; }}
QFrame#card {{ background: {PANEL}; border: 1.5px solid {BORDER}; border-radius: 14px; }}
QFrame#soon {{ background: {PANEL}; border: 1.5px dashed {BORDER}; border-radius: 16px; }}
QLabel#soonIcon {{ font-size: 40px; }}
QStatusBar {{ color: {DIM}; background: {CREAM}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""

CHATBOX_STYLE = (
    f"QLineEdit {{ background: white; color: {INK}; border: 2px solid {BORDER};"
    f" border-radius: 14px; padding: 7px 12px; font-size: 14px; }}"
    f"QLineEdit:focus {{ border-color: {ACCENT}; }}"
    f"QLineEdit:read-only {{ background: {CREAM}; color: {DIM}; }}"
)
