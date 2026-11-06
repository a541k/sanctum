"""Palettes, fonts, the global stylesheet, and icons that follow the active theme.

Design notes
- Light: cool mist desk, warm-white paper, blue-black ink as the accent.
- Dark: navy night, with a lamplight-amber accent (this is a before-bed journal).
- Sepia: a reading theme for people who like warm paper.
- Two typefaces: a serif for dates, titles and the entry text; a sans for controls.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QSize, Signal
from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QLabel

from . import icons

PALETTES: dict[str, dict[str, str]] = {
    "light": dict(label="Light", bg="#ECEEF2", surface="#FCFCFA", surface_alt="#F1F2F6", border="#D9DDE5",
                  ink="#1B2233", muted="#626B84", faint="#A2A9BA", accent="#2E4B8F", accent_ink="#FFFFFF",
                  accent_soft="#DAE3F6", hover="#E3E7EF", danger="#B3261E"),
    "dark": dict(label="Dark", bg="#0D111F", surface="#171C2E", surface_alt="#1E2438", border="#2B3352",
                 ink="#E8EAF1", muted="#9199B1", faint="#5A6482", accent="#E9B75B", accent_ink="#1B1404",
                 accent_soft="#4A3D20", hover="#232B45", danger="#FF8E85"),
    "sepia": dict(label="Sepia", bg="#E3D8C0", surface="#F4ECD9", surface_alt="#EBE0C8", border="#D1C3A3",
                  ink="#33281B", muted="#76664C", faint="#A89A7D", accent="#6B3F27", accent_ink="#FFF8EC",
                  accent_soft="#E1CEA8", hover="#DCCFB1", danger="#A32A1F"),
}

QSS = """
QWidget { font-family: "@sans"; font-size: 14px; color: @ink; }
QMainWindow, QDialog { background: @bg; }
QLabel { background: transparent; }
QToolTip { background: @surface; color: @ink; border: 1px solid @border; padding: 4px 6px; }

QLabel[role="display"] { font-family: "@serif"; font-size: 44px; color: @ink; }
QLabel[role="lead"] { font-size: 17px; color: @muted; }
QLabel[role="h1"] { font-family: "@serif"; font-size: 28px; }
QLabel[role="h2"] { font-family: "@serif"; font-size: 20px; }
QLabel[role="h3"] { font-size: 14px; font-weight: 600; color: @muted; }
QLabel[role="herotitle"] { font-family: "@serif"; font-size: 26px; }
QLabel[role="brand"] { font-family: "@serif"; font-size: 19px; }
QLabel[role="muted"] { color: @muted; }
QLabel[role="small"] { color: @muted; font-size: 12px; }
QLabel[role="error"] { color: @danger; }
QLabel[role="rowtitle"] { font-weight: 600; font-size: 15px; }
QLabel[role="tiletitle"] { font-size: 16px; font-weight: 600; }
QLabel[role="tilesub"] { color: @muted; font-size: 13px; }
QLabel[role="cardtitle"] { font-family: "@serif"; font-size: 18px; }
QLabel[role="papertime"] { color: @muted; font-size: 13px; }
QLabel[role="chip"] { background: @accent_soft; border: 1px solid transparent; border-radius: 9px; padding: 1px 9px; font-size: 12px; }
QLabel[tone="onaccent"] { color: @accent_ink; }
QLabel[role="tilesub"][tone="onaccent"] { color: @accent_ink; }

QPushButton { background: @surface; border: 1px solid @border; border-radius: 8px; padding: 8px 16px; }
QPushButton:hover { background: @hover; }
QPushButton:pressed { background: @accent_soft; }
QPushButton:focus { border: 1px solid @accent; }
QPushButton:disabled { color: @faint; background: @surface_alt; }
QPushButton[role="primary"] { background: @accent; color: @accent_ink; border: 1px solid @accent; font-weight: 600; }
QPushButton[role="primary"]:hover { border: 1px solid @ink; background: @accent; }
QPushButton[role="primary"]:disabled { background: @surface_alt; color: @faint; border: 1px solid @border; }
QPushButton[role="danger"] { color: @danger; }
QPushButton[role="ghost"] { background: transparent; border: none; padding: 7px 11px; color: @muted; }
QPushButton[role="ghost"]:hover { background: @hover; color: @ink; }
QPushButton[role="ghost"]:focus { border: none; background: @hover; }

QPushButton[role="tile"] { background: @surface; border: 1px solid @border; border-radius: 14px; padding: 0; text-align: left; }
QPushButton[role="tile"]:hover, QPushButton[role="tile"]:focus { border: 1px solid @accent; background: @surface; }
QPushButton[role="hero"] { background: @accent; border: 1px solid @accent; border-radius: 18px; padding: 0; text-align: left; }
QPushButton[role="hero"]:hover, QPushButton[role="hero"]:focus { border: 1px solid @ink; background: @accent; }

QFrame#segbar { background: @surface_alt; border: 1px solid @border; border-radius: 12px; }
QPushButton[role="seg"] { background: transparent; border: 1px solid transparent; border-radius: 9px; padding: 7px 20px; color: @muted; }
QPushButton[role="seg"]:hover { color: @ink; background: transparent; }
QPushButton[role="seg"]:checked { background: @surface; border: 1px solid @border; color: @ink; font-weight: 600; }

QPushButton[role="choice"] { background: @surface; border: 2px solid @border; border-radius: 12px; padding: 10px 18px 10px 12px; text-align: left; min-width: 96px; }
QPushButton[role="choice"]:checked { border: 2px solid @accent; background: @accent_soft; font-weight: 600; }

QPushButton[cal="day"] { background: transparent; border: 1px solid transparent; border-radius: 9px; padding: 0; color: @ink; }
QPushButton[cal="day"]:hover { background: @hover; }
QPushButton[cal="day"][other="true"] { color: @faint; }
QPushButton[cal="day"][entry="true"] { background: @accent_soft; font-weight: 700; }
QPushButton[cal="day"][today="true"] { border: 1px solid @accent; }
QPushButton[cal="day"][selected="true"] { background: @accent; color: @accent_ink; font-weight: 700; border: 1px solid @accent; }
QPushButton[cal="day"]:focus { border: 1px solid @ink; }

QFrame#topbar { background: @surface; border: none; border-bottom: 1px solid @border; border-radius: 0; }
QFrame[card="true"] { background: @surface; border: 1px solid @border; border-radius: 12px; }
QFrame[card="true"][clickable="true"]:hover, QFrame[card="true"][clickable="true"]:focus { border: 1px solid @accent; }
QFrame[paper="true"] { background: @surface; border: 1px solid @border; border-radius: 6px; }
QFrame[divider="true"] { background: @border; border: none; min-height: 1px; max-height: 1px; }
QFrame[vdivider="true"] { background: @border; border: none; min-width: 1px; max-width: 1px; }

QLineEdit { background: @surface; border: 1px solid @border; border-radius: 8px; padding: 8px 10px;
            selection-background-color: @accent; selection-color: @accent_ink; }
QLineEdit:focus { border: 1px solid @accent; }
QLineEdit[bare="true"] { background: transparent; border: none; border-bottom: 1px solid @border; border-radius: 0; padding: 7px 2px; }
QLineEdit[bare="true"]:focus { border: none; border-bottom: 1px solid @accent; }
QLineEdit[bare="title"] { background: transparent; border: none; border-bottom: 1px solid @border; border-radius: 0;
                          padding: 7px 2px; font-family: "@serif"; font-size: 24px; }
QLineEdit[bare="title"]:focus { border: none; border-bottom: 1px solid @accent; }

QTextEdit[paper="true"] { background: transparent; border: none; font-family: "@serif"; font-size: 14pt;
                          selection-background-color: @accent; selection-color: @accent_ink; }
QPlainTextEdit { background: @surface_alt; border: 1px solid @border; border-radius: 8px; padding: 8px;
                 font-family: "Consolas"; font-size: 15px; }

QToolButton[role="fmt"] { background: transparent; border: none; border-radius: 6px; padding: 5px 10px; color: @muted; font-weight: 600; }
QToolButton[role="fmt"]:hover { background: @hover; color: @ink; }
QToolButton[role="fmt"]:checked { background: @accent_soft; color: @ink; }

QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 10px 12px; border-radius: 8px; color: @ink; }
QListWidget::item:hover { background: @hover; }
QListWidget::item:selected { background: @accent_soft; color: @ink; }

QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: @border; border-radius: 4px; min-height: 36px; }
QScrollBar::handle:vertical:hover { background: @faint; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }
"""


def pick_font(candidates: list[str], fallback: str) -> str:
    available = set(QFontDatabase.families())
    for name in candidates:
        if name in available:
            return name
    return fallback


def build_qss(p: dict[str, str], serif: str, sans: str) -> str:
    tokens = dict(p, serif=serif, sans=sans)
    out = QSS
    for key in sorted(tokens, key=len, reverse=True):  # longest first: @surface_alt before @surface
        out = out.replace("@" + key, tokens[key])
    return out


def make_palette(p: dict[str, str]) -> QPalette:
    pal = QPalette()
    R = QPalette.ColorRole
    pairs = {R.Window: "bg", R.WindowText: "ink", R.Base: "surface", R.AlternateBase: "surface_alt",
             R.Text: "ink", R.Button: "surface", R.ButtonText: "ink", R.Highlight: "accent",
             R.HighlightedText: "accent_ink", R.ToolTipBase: "surface", R.ToolTipText: "ink",
             R.PlaceholderText: "faint", R.Link: "accent"}
    for role, key in pairs.items():
        pal.setColor(role, QColor(p[key]))
    for role in (R.Text, R.WindowText, R.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(p["faint"]))
    return pal


class ThemeManager(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.name = "light"
        self.p = PALETTES["light"]
        self.serif = "Georgia"
        self.sans = "Segoe UI"

    def init_fonts(self) -> None:
        self.serif = pick_font(["Sitka Text", "Constantia", "Palatino Linotype", "Georgia", "Cambria"], "Georgia")
        self.sans = pick_font(["Segoe UI", "Inter", "Helvetica Neue", "Arial"], QApplication.font().family())

    def apply(self, name: str) -> None:
        if name not in PALETTES:
            name = "light"
        self.name, self.p = name, PALETTES[name]
        app = QApplication.instance()
        if app.style().objectName().lower() != "fusion":
            app.setStyle("Fusion")
        app.setPalette(make_palette(self.p))
        app.setStyleSheet(build_qss(self.p, self.serif, self.sans))
        self.changed.emit()


THEME = ThemeManager()


class _IconBinder(QObject):
    """Keeps a button/label icon in sync with the theme colour."""

    def __init__(self, widget, name: str, color_key: str, size: int):
        super().__init__(widget)
        self.widget, self.name, self.color_key, self.size = widget, name, color_key, size
        THEME.changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        color = THEME.p[self.color_key]
        if isinstance(self.widget, QLabel):
            self.widget.setPixmap(icons.pixmap(self.name, color, self.size))
        else:
            self.widget.setIcon(icons.icon(self.name, color, self.size))
            self.widget.setIconSize(QSize(self.size, self.size))


def bind_icon(widget, name: str, color_key: str = "muted", size: int = 20) -> None:
    _IconBinder(widget, name, color_key, size)
