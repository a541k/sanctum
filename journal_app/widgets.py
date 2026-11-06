"""Reusable widgets: calendar, entry cards and list, home tiles, layout helpers."""
from __future__ import annotations

import calendar
from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget, QGridLayout,
)

from .theme import bind_icon
from .vault import Summary

AlignCenter = Qt.AlignmentFlag.AlignCenter
NoMouse = Qt.WidgetAttribute.WA_TransparentForMouseEvents


def repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)


def make_label(text: str = "", role: str | None = None, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    label.setWordWrap(wrap)
    return label


def make_button(text: str, role: str | None = None, icon: str | None = None,
                icon_color: str = "muted", icon_size: int = 18) -> QPushButton:
    btn = QPushButton(text)
    if role:
        btn.setProperty("role", role)
    if icon:
        bind_icon(btn, icon, icon_color, icon_size)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def make_scroll(inner: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(inner)
    scroll.viewport().setAutoFillBackground(False)
    inner.setAutoFillBackground(False)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    return scroll


def centered(widget: QWidget, max_width: int) -> QWidget:
    """Centre content in a column that never gets wider than max_width."""
    host = QWidget()
    lay = QHBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    widget.setMaximumWidth(max_width)
    lay.addStretch(1)
    lay.addWidget(widget, 100)
    lay.addStretch(1)
    return host


def divider() -> QFrame:
    line = QFrame()
    line.setProperty("divider", "true")
    return line


def card_frame() -> QFrame:
    frame = QFrame()
    frame.setProperty("card", "true")
    return frame


# --------------------------------------------------------------------------
class Tile(QPushButton):
    """A large menu button: icon, title and a one-line description."""

    def __init__(self, icon_name: str, title: str, subtitle: str = "", hero: bool = False):
        super().__init__()
        self.setProperty("role", "hero" if hero else "tile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(104 if hero else 118)
        tone = "onaccent" if hero else None

        icon = QLabel()
        icon.setAttribute(NoMouse)
        bind_icon(icon, icon_name, "accent_ink" if hero else "accent", 30 if hero else 26)
        name = make_label(title, "tiletitle")
        name.setAttribute(NoMouse)
        sub = make_label(subtitle, "tilesub", wrap=True)
        sub.setAttribute(NoMouse)
        if hero:
            name.setProperty("role", "herotitle")
        if tone:
            for lbl in (name, sub):
                lbl.setProperty("tone", tone)

        text = QVBoxLayout()
        text.setSpacing(3)
        text.addWidget(name)
        if subtitle:
            text.addWidget(sub)

        if hero:
            lay = QHBoxLayout(self)
            lay.setContentsMargins(26, 18, 26, 18)
            lay.setSpacing(18)
            lay.addWidget(icon)
            lay.addLayout(text, 1)
        else:
            lay = QVBoxLayout(self)
            lay.setContentsMargins(20, 18, 20, 18)
            lay.setSpacing(10)
            lay.addWidget(icon)
            lay.addLayout(text)
            lay.addStretch()


# --------------------------------------------------------------------------
class EntryCard(QFrame):
    clicked = Signal(str)

    def __init__(self, s: Summary, show_date: bool):
        super().__init__()
        self.entry_id = s.id
        self.setProperty("card", "true")
        self.setProperty("clickable", "true")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        c = s.created
        when = f"{c:%I:%M %p}".lstrip("0")
        if show_date:
            when = f"{c:%a} {c.day} {c:%b %Y}, {when}"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(3)
        parts = [make_label(when, "small"), make_label(s.title or "Untitled", "cardtitle")]
        if s.preview:
            parts.append(make_label(s.preview, "muted", wrap=True))
        for p in parts:
            p.setAttribute(NoMouse)
            lay.addWidget(p)
        if s.tags:
            row = QHBoxLayout()
            row.setSpacing(6)
            row.setContentsMargins(0, 5, 0, 0)
            for t in s.tags:
                chip = make_label(f"#{t}", "chip")
                chip.setAttribute(NoMouse)
                row.addWidget(chip)
            row.addStretch()
            lay.addLayout(row)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.entry_id)
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit(self.entry_id)
        else:
            super().keyPressEvent(e)


class EntryList(QWidget):
    """Scrollable stack of entry cards."""
    entryChosen = Signal(str)

    def __init__(self):
        super().__init__()
        self.body = QWidget()
        self.vbox = QVBoxLayout(self.body)
        self.vbox.setContentsMargins(0, 0, 10, 0)
        self.vbox.setSpacing(10)
        self.vbox.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(make_scroll(self.body))

    def set_entries(self, rows: list[Summary], show_date: bool = True, empty: str = "No entries.") -> None:
        while self.vbox.count() > 1:
            item = self.vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not rows:
            msg = make_label(empty, "muted", wrap=True)
            msg.setContentsMargins(2, 8, 2, 8)
            self.vbox.insertWidget(0, msg)
            return
        for i, s in enumerate(rows):
            card = EntryCard(s, show_date)
            card.clicked.connect(self.entryChosen)
            self.vbox.insertWidget(i, card)


# --------------------------------------------------------------------------
class CalendarWidget(QWidget):
    """Month grid where every day is a button. Days with entries are tinted."""
    dateSelected = Signal(str)       # ISO date, emitted when the user picks a day
    monthChanged = Signal(int, int)  # year, month

    def __init__(self):
        super().__init__()
        today = date.today()
        self.year, self.month = today.year, today.month
        self.selected = today.isoformat()
        self.marked: set[str] = set()
        self._cal = calendar.Calendar(firstweekday=6)  # weeks start on Sunday

        prev_btn = make_button("", "ghost", "chevron_left", "ink", 20)
        prev_btn.setToolTip("Previous month")
        next_btn = make_button("", "ghost", "chevron_right", "ink", 20)
        next_btn.setToolTip("Next month")
        today_btn = make_button("Today", "ghost")
        self.title = make_label("", "h2")
        self.title.setAlignment(AlignCenter)
        prev_btn.clicked.connect(lambda: self._shift(-1))
        next_btn.clicked.connect(lambda: self._shift(1))
        today_btn.clicked.connect(self._go_today)

        head = QHBoxLayout()
        head.addWidget(prev_btn)
        head.addWidget(self.title, 1)
        head.addWidget(today_btn)
        head.addWidget(next_btn)

        grid = QGridLayout()
        grid.setSpacing(4)
        for i in range(7):
            lbl = make_label(calendar.day_abbr[(6 + i) % 7], "small")
            lbl.setAlignment(AlignCenter)
            grid.addWidget(lbl, 0, i)
        self.cells: list[list[QPushButton]] = []
        for r in range(6):
            row = []
            for c in range(7):
                b = QPushButton()
                b.setProperty("cal", "day")
                b.setFixedSize(42, 42)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.clicked.connect(lambda _=False, btn=b: self._clicked(btn.property("iso")))
                grid.addWidget(b, r + 1, c)
                row.append(b)
            self.cells.append(row)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addLayout(head)
        lay.addLayout(grid)
        self._rebuild()

    @staticmethod
    def _flag(v: bool) -> str:
        return "true" if v else "false"

    def _rebuild(self) -> None:
        self.title.setText(f"{calendar.month_name[self.month]} {self.year}")
        weeks = self._cal.monthdatescalendar(self.year, self.month)
        while len(weeks) < 6:  # keep a constant height
            last = weeks[-1][-1]
            weeks.append([last + timedelta(days=i + 1) for i in range(7)])
        today = date.today().isoformat()
        for r, week in enumerate(weeks):
            for c, d in enumerate(week):
                b, iso = self.cells[r][c], d.isoformat()
                b.setText(str(d.day))
                b.setProperty("iso", iso)
                b.setProperty("other", self._flag(d.month != self.month))
                b.setProperty("entry", self._flag(iso in self.marked))
                b.setProperty("today", self._flag(iso == today))
                b.setProperty("selected", self._flag(iso == self.selected))
                b.setToolTip("Has entries" if iso in self.marked else "")
                repolish(b)

    def set_marked(self, iso_dates: set[str]) -> None:
        self.marked = set(iso_dates)
        self._rebuild()

    def set_date(self, iso: str) -> None:
        """Move to a date without emitting dateSelected (still emits monthChanged if needed)."""
        d = date.fromisoformat(iso)
        month_changed = (d.year, d.month) != (self.year, self.month)
        self.year, self.month, self.selected = d.year, d.month, iso
        self._rebuild()
        if month_changed:
            self.monthChanged.emit(self.year, self.month)

    def _clicked(self, iso: str) -> None:
        self.set_date(iso)
        self.dateSelected.emit(iso)

    def _shift(self, delta: int) -> None:
        idx = self.year * 12 + (self.month - 1) + delta
        self.year, self.month = idx // 12, idx % 12 + 1
        self._rebuild()
        self.monthChanged.emit(self.year, self.month)

    def _go_today(self) -> None:
        self._clicked(date.today().isoformat())
