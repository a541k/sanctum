"""The diary page: date header, title, tags, formatting toolbar and writing area."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QKeySequence, QTextCharFormat, QTextCursor, QTextListFormat
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QTextEdit, QToolButton, QVBoxLayout, QWidget

from .vault import Entry, parse_tag_string
from .widgets import divider, make_button, make_label

BOLD, NORMAL = 700, 400
HEADING_PT = {0: 14, 1: 26, 2: 20}


class EntryEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.entry: Entry | None = None
        self.is_new = False
        self.dirty = False
        self._loading = False

        # --- the sheet of paper ---
        self.date_label = make_label("", "h1")
        self.time_label = make_label("", "papertime")
        self.title = QLineEdit()
        self.title.setProperty("bare", "title")
        self.title.setPlaceholderText("Title (optional)")
        self.tags = QLineEdit()
        self.tags.setProperty("bare", "true")
        self.tags.setPlaceholderText("Tags, separated by commas (optional)")
        self.text = QTextEdit()
        self.text.setProperty("paper", "true")
        self.text.setAcceptRichText(False)  # paste as plain text; format with the toolbar
        self.text.setPlaceholderText("Write about your day…")
        self.text.document().setDocumentMargin(4)

        paper = QFrame()
        paper.setProperty("paper", "true")
        pl = QVBoxLayout(paper)
        pl.setContentsMargins(40, 30, 40, 24)
        pl.setSpacing(6)
        pl.addWidget(self.date_label)
        pl.addWidget(self.time_label)
        pl.addSpacing(10)
        pl.addWidget(self.title)
        pl.addWidget(self.tags)
        pl.addSpacing(6)
        pl.addLayout(self._build_toolbar())
        pl.addWidget(divider())
        pl.addSpacing(6)
        pl.addWidget(self.text, 1)

        # --- actions under the paper ---
        self.status = make_label("", "small")
        self.delete_btn = make_button("Delete entry", "danger", "trash", "danger")
        self.save_btn = make_button("Save entry", "primary", "check", "accent_ink")
        bottom = QHBoxLayout()
        bottom.addWidget(self.status)
        bottom.addStretch()
        bottom.addWidget(self.delete_btn)
        bottom.addWidget(self.save_btn)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        lay.addWidget(paper, 1)
        lay.addLayout(bottom)

        self.text.document().contentsChanged.connect(self._mark_dirty)
        self.title.textEdited.connect(self._mark_dirty)
        self.tags.textEdited.connect(self._mark_dirty)
        self.text.currentCharFormatChanged.connect(self._sync_format_buttons)

    # ---- toolbar ---------------------------------------------------------
    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(2)

        def add(label, tip, slot, shortcut=None, checkable=False, font=None) -> QAction:
            act = QAction(label, self)
            act.setCheckable(checkable)
            act.setToolTip(tip + (f" ({shortcut})" if shortcut else ""))
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
                act.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            act.triggered.connect(slot)
            self.addAction(act)
            btn = QToolButton()
            btn.setProperty("role", "fmt")
            btn.setDefaultAction(act)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if font:
                btn.setFont(font)
            row.addWidget(btn)
            return act

        ital, strike = QFont(), QFont()
        ital.setItalic(True)
        strike.setStrikeOut(True)
        self.act_bold = add("B", "Bold", self.toggle_bold, "Ctrl+B", True)
        self.act_italic = add("I", "Italic", self.toggle_italic, "Ctrl+I", True, ital)
        self.act_strike = add("S", "Strikethrough", self.toggle_strike, None, True, strike)
        row.addSpacing(8)
        add("H1", "Large heading", lambda: self.set_heading(1))
        add("H2", "Small heading", lambda: self.set_heading(2))
        row.addSpacing(8)
        add("• List", "Bulleted list", lambda: self.toggle_list(QTextListFormat.Style.ListDisc))
        add("1. List", "Numbered list", lambda: self.toggle_list(QTextListFormat.Style.ListDecimal))
        row.addSpacing(8)
        add("Undo", "Undo", self.text.undo)
        add("Redo", "Redo", self.text.redo)
        row.addStretch()
        return row

    def _sync_format_buttons(self, fmt: QTextCharFormat) -> None:
        self.act_bold.setChecked(fmt.fontWeight() >= 600)
        self.act_italic.setChecked(fmt.fontItalic())
        self.act_strike.setChecked(fmt.fontStrikeOut())

    def toggle_bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(NORMAL if self.text.fontWeight() >= 600 else BOLD)
        self.text.mergeCurrentCharFormat(fmt)
        self.text.setFocus()

    def toggle_italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.text.fontItalic())
        self.text.mergeCurrentCharFormat(fmt)
        self.text.setFocus()

    def toggle_strike(self):
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not self.text.currentCharFormat().fontStrikeOut())
        self.text.mergeCurrentCharFormat(fmt)
        self.text.setFocus()

    def set_heading(self, level: int):
        cur = self.text.textCursor()
        bf = cur.blockFormat()
        level = 0 if bf.headingLevel() == level else level  # pressing again removes it
        cur.beginEditBlock()
        bf.setHeadingLevel(level)
        cur.setBlockFormat(bf)
        cur.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cur.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        fmt = QTextCharFormat()
        fmt.setFontPointSize(HEADING_PT[level])
        fmt.setFontWeight(BOLD if level else NORMAL)
        cur.mergeCharFormat(fmt)
        cur.endEditBlock()
        self.text.setFocus()

    def toggle_list(self, style):
        cur = self.text.textCursor()
        current = cur.currentList()
        cur.beginEditBlock()
        if current is not None and current.format().style() == style:
            current.remove(cur.block())
            bf = cur.blockFormat()
            bf.setIndent(0)
            cur.setBlockFormat(bf)
        else:
            fmt = QTextListFormat()
            fmt.setStyle(style)
            cur.createList(fmt)
        cur.endEditBlock()
        self.text.setFocus()

    # ---- state -----------------------------------------------------------
    def _mark_dirty(self):
        if not self._loading:
            self.dirty = True
            self.status.setText("Unsaved changes")

    def load(self, entry: Entry, is_new: bool) -> None:
        self._loading = True
        self.entry, self.is_new = entry, is_new
        c = entry.created
        self.date_label.setText(f"{c:%A}, {c.day} {c:%B %Y}")
        self.time_label.setText(f"{c:%I:%M %p}".lstrip("0"))
        self.title.setText(entry.title)
        self.tags.setText(", ".join(entry.tags))
        self.text.setMarkdown(entry.content)
        self.text.document().clearUndoRedoStacks()
        self.delete_btn.setVisible(not is_new)
        self.dirty = False
        self.status.setText("New entry. It is saved when you press Save." if is_new else "")
        self._loading = False
        self.text.moveCursor(QTextCursor.MoveOperation.End)
        self.text.setFocus()

    def collect(self) -> Entry:
        e = self.entry
        e.title = self.title.text().strip()
        e.tags = parse_tag_string(self.tags.text())
        e.content = self.text.document().toMarkdown().rstrip() + "\n"
        return e

    def mark_saved(self) -> None:
        self.dirty, self.is_new = False, False
        self.delete_btn.setVisible(True)
        self.status.setText("Saved")
        self.tags.setText(", ".join(self.entry.tags))

    def clear(self) -> None:
        self._loading = True
        self.entry, self.dirty = None, False
        self.title.clear()
        self.tags.clear()
        self.text.clear()
        self._loading = False
