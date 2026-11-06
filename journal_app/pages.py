"""The screens of the app. Each page is a widget the main window swaps in."""
from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QListWidget, QListWidgetItem,
    QMessageBox, QStackedWidget, QVBoxLayout, QWidget,
)

from .dialogs import NewPasswordDialog
from .theme import PALETTES, THEME
from .vault import Entry
from .widgets import (
    CalendarWidget, EntryList, Tile, card_frame, centered, divider, make_button, make_label, make_scroll,
)
from .editor import EntryEditor


class Page(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win

    def on_show(self) -> None:
        """Called every time the page becomes visible. Refresh data here."""

    def can_leave(self) -> bool:
        return True


def _relative_day(iso: str) -> str:
    days = (date.today() - date.fromisoformat(iso)).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    d = date.fromisoformat(iso)
    return f"on {d.day} {d:%B %Y}"


# --------------------------------------------------------------------------
class HomePage(Page):
    def __init__(self, win):
        super().__init__(win)
        col = QWidget()
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 40, 0, 40)
        lay.setSpacing(0)

        self.lead = make_label("", "lead")
        self.date = make_label("", "display")
        self.stats = make_label("", "muted")
        lay.addWidget(self.lead)
        lay.addWidget(self.date)
        lay.addSpacing(4)
        lay.addWidget(self.stats)
        lay.addSpacing(30)

        hero = Tile("edit", "New entry", "Write about today. The date and time are filled in for you.", hero=True)
        hero.clicked.connect(lambda: win.new_entry())
        lay.addWidget(hero)
        lay.addSpacing(30)

        lay.addWidget(make_label("Browse", "h3"))
        lay.addSpacing(10)
        row = QHBoxLayout()
        row.setSpacing(14)
        for icon, title, sub, tab in (
            ("calendar", "By date", "Pick a day on the calendar", 0),
            ("tag", "By tag", "See entries grouped by topic", 1),
            ("list", "All entries", "Everything, newest first", 2),
        ):
            t = Tile(icon, title, sub)
            t.clicked.connect(lambda _=False, i=tab: win.show_browse(i))
            row.addWidget(t)
        lay.addLayout(row)
        lay.addSpacing(30)

        row2 = QHBoxLayout()
        row2.setSpacing(14)
        settings = Tile("settings", "Settings", "Password, backup, storage and theme")
        settings.clicked.connect(lambda: win.show_settings())
        lock = Tile("lock", "Lock", "Close the journal until you unlock it again")
        lock.clicked.connect(lambda: win.lock())
        row2.addWidget(settings)
        row2.addWidget(lock)
        lay.addLayout(row2)
        lay.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 0, 40, 0)
        outer.addWidget(make_scroll(centered(col, 840)))

    def on_show(self) -> None:
        now = datetime.now()
        part = "morning" if now.hour < 12 else "afternoon" if now.hour < 18 else "evening"
        self.lead.setText(f"{now:%A} {part}")
        self.date.setText(f"{now.day} {now:%B %Y}")
        v = self.win.vault
        n = v.entry_count()
        if n == 0:
            self.stats.setText("No entries yet. Start with a new entry.")
        else:
            self.stats.setText(f"{n} {'entry' if n == 1 else 'entries'} so far. "
                               f"Last written {_relative_day(v.latest_date())}.")


# --------------------------------------------------------------------------
class BrowsePage(Page):
    TABS = ("By date", "By tag", "All entries")

    def __init__(self, win):
        super().__init__(win)
        self.current_date = date.today().isoformat()
        self.current_tag: str | None = None

        seg = QFrame()
        seg.setObjectName("segbar")
        sl = QHBoxLayout(seg)
        sl.setContentsMargins(4, 4, 4, 4)
        sl.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, text in enumerate(self.TABS):
            b = make_button(text, "seg")
            b.setCheckable(True)
            self.group.addButton(b, i)
            sl.addWidget(b)
        self.group.idClicked.connect(self.show_tab)

        self.views = QStackedWidget()
        self.views.addWidget(self._build_date_view())
        self.views.addWidget(self._build_tag_view())
        self.views.addWidget(self._build_all_view())

        top = QHBoxLayout()
        top.addStretch()
        top.addWidget(seg)
        top.addStretch()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 26, 40, 24)
        lay.setSpacing(22)
        lay.addLayout(top)
        lay.addWidget(self.views, 1)
        self.show_tab(0)

    # -- views --
    def _build_date_view(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setSpacing(32)
        self.calendar = CalendarWidget()
        card = card_frame()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 20)
        cl.addWidget(self.calendar)
        self.day_title = make_label("", "h1")
        self.day_list = EntryList()
        self.day_list.entryChosen.connect(lambda i: self.win.open_entry(i))
        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(self.day_title)
        right.addWidget(self.day_list, 1)
        h.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
        h.addLayout(right, 1)
        self.calendar.dateSelected.connect(self._show_day)
        self.calendar.monthChanged.connect(lambda y, m: self._refresh_marks())
        return w

    def _build_tag_view(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setSpacing(32)
        self.tag_list = QListWidget()
        self.tag_list.itemClicked.connect(lambda item: self._show_tag(item.data(Qt.ItemDataRole.UserRole)))
        card = card_frame()
        card.setFixedWidth(300)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(10, 10, 10, 10)
        cl.addWidget(self.tag_list)
        self.tag_title = make_label("", "h1")
        self.tag_list_entries = EntryList()
        self.tag_list_entries.entryChosen.connect(lambda i: self.win.open_entry(i))
        right = QVBoxLayout()
        right.setSpacing(12)
        right.addWidget(self.tag_title)
        right.addWidget(self.tag_list_entries, 1)
        h.addWidget(card)
        h.addLayout(right, 1)
        return w

    def _build_all_view(self) -> QWidget:
        w = QWidget()
        self.all_title = make_label("All entries", "h1")
        self.all_entries = EntryList()
        self.all_entries.entryChosen.connect(lambda i: self.win.open_entry(i))
        col = QVBoxLayout()
        col.setSpacing(12)
        col.addWidget(self.all_title)
        col.addWidget(self.all_entries, 1)
        host = QWidget()
        host.setLayout(col)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(centered(host, 860))
        return w

    # -- behaviour --
    def show_tab(self, i: int) -> None:
        self.group.button(i).setChecked(True)
        self.views.setCurrentIndex(i)

    def on_show(self) -> None:
        self.calendar.set_date(self.current_date)
        self._refresh_marks()
        self._show_day(self.current_date)
        self._refresh_tags()
        self._refresh_all()

    def _refresh_marks(self) -> None:
        v, y, m = self.win.vault, self.calendar.year, self.calendar.month
        marks = set()
        for dy, dm in ((y, m), (y - 1 if m == 1 else y, 12 if m == 1 else m - 1),
                       (y + 1 if m == 12 else y, 1 if m == 12 else m + 1)):  # include visible neighbours
            marks |= v.dates_in_month(dy, dm)
        self.calendar.set_marked(marks)

    def _show_day(self, iso: str) -> None:
        self.current_date = iso
        d = date.fromisoformat(iso)
        self.day_title.setText(f"{d:%A}, {d.day} {d:%B %Y}")
        self.day_list.set_entries(self.win.vault.entries_for_date(iso), show_date=False,
                                  empty="No entries on this day.")

    def _refresh_tags(self) -> None:
        tags = self.win.vault.all_tags()
        self.tag_list.clear()
        for tag, n in tags:
            item = QListWidgetItem(f"#{tag}    {n}")
            item.setData(Qt.ItemDataRole.UserRole, tag)
            self.tag_list.addItem(item)
        names = [t for t, _ in tags]
        if self.current_tag not in names:
            self.current_tag = None
        if self.current_tag:
            self.tag_list.setCurrentRow(names.index(self.current_tag))
            self._show_tag(self.current_tag)
        else:
            self.tag_title.setText("Tags")
            self.tag_list_entries.set_entries(
                [], empty=("Pick a tag on the left to see its entries." if tags
                           else "No tags yet. Add tags to an entry when you write it."))

    def _show_tag(self, tag: str) -> None:
        self.current_tag = tag
        self.tag_title.setText(f"#{tag}")
        self.tag_list_entries.set_entries(self.win.vault.entries_for_tag(tag))

    def _refresh_all(self) -> None:
        rows = self.win.vault.all_entries()
        self.all_title.setText(f"All entries ({len(rows)})")
        self.all_entries.set_entries(rows, empty="No entries yet. Start with a new entry.")


# --------------------------------------------------------------------------
class EntryPage(Page):
    def __init__(self, win):
        super().__init__(win)
        self.editor = EntryEditor()
        self.editor.save_btn.clicked.connect(self.save)
        self.editor.delete_btn.clicked.connect(self.delete)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 24, 40, 24)
        lay.addWidget(centered(self.editor, 900))

    def open_new(self) -> None:
        self.editor.load(Entry.new(), is_new=True)  # timestamp is taken now

    def open_existing(self, entry_id: str) -> None:
        self.editor.load(self.win.vault.get_entry(entry_id), is_new=False)

    def can_leave(self) -> bool:
        if not (self.editor.entry and self.editor.dirty):
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Unsaved changes")
        box.setText("Save this entry before leaving?")
        box.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                               | QMessageBox.StandardButton.Cancel)
        choice = box.exec()
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        if choice == QMessageBox.StandardButton.Save:
            self.save()
        return True

    def save(self) -> None:
        if not self.editor.entry:
            return
        self.editor.entry = self.win.vault.save_entry(self.editor.collect())
        self.editor.mark_saved()

    def _confirm_delete(self) -> bool:
        box = QMessageBox(QMessageBox.Icon.Warning, "Delete entry",
                          "Delete this entry permanently? This can't be undone.", parent=self)
        delete = box.addButton("Delete entry", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Keep entry", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.exec()
        return box.clickedButton() is delete

    def delete(self) -> None:
        e = self.editor.entry
        if not e or self.editor.is_new:
            return
        if not self._confirm_delete():
            return
        self.win.vault.delete_entry(e.id)
        self.editor.clear()
        self.win.go_back()


# --------------------------------------------------------------------------
class Section(QWidget):
    """A titled card holding one or more setting rows."""

    def __init__(self, title: str):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        v.addWidget(make_label(title, "h2"))
        self.card = card_frame()
        self.body = QVBoxLayout(self.card)
        self.body.setContentsMargins(22, 18, 22, 18)
        self.body.setSpacing(16)
        v.addWidget(self.card)

    def add_row(self, title: str, desc: str, *buttons, desc_selectable: bool = False):
        if self.body.count():
            self.body.addWidget(divider())
        row = QHBoxLayout()
        row.setSpacing(18)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(make_label(title, "rowtitle"))
        d = make_label(desc, "muted", wrap=True)
        if desc_selectable:
            d.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.addWidget(d)
        row.addLayout(text, 1)
        for b in buttons:
            row.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
        self.body.addLayout(row)
        return d


def _swatch(name: str) -> QPixmap:
    p = PALETTES[name]
    pm = QPixmap(52 * 2, 34 * 2)
    pm.fill(Qt.GlobalColor.transparent)
    g = QPainter(pm)
    g.setRenderHint(QPainter.RenderHint.Antialiasing)
    g.setPen(QColor(p["border"]))
    g.setBrush(QColor(p["bg"]))
    g.drawRoundedRect(2, 2, 100, 64, 12, 12)
    g.setPen(Qt.PenStyle.NoPen)
    g.setBrush(QColor(p["surface"]))
    g.drawRoundedRect(14, 14, 50, 40, 6, 6)
    g.setBrush(QColor(p["accent"]))
    g.drawEllipse(74, 20, 18, 18)
    g.end()
    pm.setDevicePixelRatio(2)
    return pm


class SettingsPage(Page):
    BACKUP_TEXT = ("Save a copy of your journal as a .zip file. It stays encrypted, "
                   "so you still need your password to read it.")

    def __init__(self, win):
        super().__init__(win)
        col = QWidget()
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 30, 0, 36)
        lay.setSpacing(26)
        lay.addWidget(make_label("Settings", "h1"))

        # Security
        sec = Section("Security")
        pw_btn = make_button("Change password…")
        pw_btn.clicked.connect(self.change_password)
        sec.add_row("Password", "The password you use to unlock your journal.", pw_btn)
        lay.addWidget(sec)

        # Backup
        bak = Section("Backup")
        export_btn = make_button("Export…", icon="download", icon_color="ink")
        export_btn.clicked.connect(self.export_backup)
        self.backup_desc = bak.add_row(
            "Export a backup", self.BACKUP_TEXT + " No backup yet.", export_btn)
        cloud_btn = make_button("Coming soon", icon="cloud")
        cloud_btn.setEnabled(False)
        bak.add_row("Google Drive sync", "Keep an encrypted copy of your journal in your own Google Drive.", cloud_btn)
        lay.addWidget(bak)

        # Storage
        sto = Section("Storage")
        open_btn = make_button("Open folder", icon="folder", icon_color="ink")
        open_btn.clicked.connect(self.open_folder)
        move_btn = make_button("Change location…")
        move_btn.clicked.connect(self.change_location)
        self.path_desc = sto.add_row("Journal folder", "", open_btn, move_btn, desc_selectable=True)
        lay.addWidget(sto)

        # Appearance
        app_sec = Section("Appearance")
        choices = QHBoxLayout()
        choices.setSpacing(12)
        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_buttons = {}
        for name, p in PALETTES.items():
            b = make_button(p["label"], "choice")
            b.setCheckable(True)
            b.setIcon(_swatch(name))
            b.setIconSize(QSize(52, 34))
            b.clicked.connect(lambda _=False, n=name: self.set_theme(n))
            self.theme_group.addButton(b)
            self.theme_buttons[name] = b
            choices.addWidget(b)
        choices.addStretch()
        wrap = QWidget()
        wrap.setLayout(choices)
        app_sec.body.addWidget(make_label("Theme", "rowtitle"))
        app_sec.body.addWidget(wrap)
        lay.addWidget(app_sec)
        lay.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 0, 40, 0)
        outer.addWidget(make_scroll(centered(col, 760)))

    def on_show(self) -> None:
        self.path_desc.setText(str(self.win.vault.root))
        last = self.win.config.last_backup
        self.backup_desc.setText(self.BACKUP_TEXT + (f" Last backup: {last}." if last else " No backup yet."))
        self.theme_buttons.get(THEME.name, self.theme_buttons["light"]).setChecked(True)

    # -- actions --
    def change_password(self) -> None:
        v = self.win.vault
        dlg = NewPasswordDialog("Change password", "Your entries stay as they are. Only the password changes.",
                                verify=v.verify_password, parent=self)
        if dlg.exec() == NewPasswordDialog.DialogCode.Accepted:
            v.change_password(dlg.password)
            QMessageBox.information(self, "Password changed", "Your password has been changed.")

    def export_backup(self) -> None:
        default = f"journal-backup-{date.today().isoformat()}.zip"
        path, _ = QFileDialog.getSaveFileName(self, "Export backup", str(self.win.config.vault_path.parent / default),
                                              "Zip archive (*.zip)")
        if not path:
            return
        try:
            n = self.win.vault.export_backup(path)
        except OSError as ex:
            QMessageBox.warning(self, "Backup failed", f"Couldn't write the backup file:\n{ex}")
            return
        self.win.config.last_backup = datetime.now().strftime("%d %b %Y, %I:%M %p").lstrip("0")
        self.win.config.save()
        self.on_show()
        QMessageBox.information(self, "Backup saved", f"Saved {n} {'entry' if n == 1 else 'entries'} to:\n{path}")

    def open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.win.vault.root)))

    def change_location(self) -> None:
        start = str(self.win.vault.root.parent)
        folder = QFileDialog.getExistingDirectory(self, "Choose an empty folder for your journal", start)
        if not folder:
            return
        ok = QMessageBox.question(
            self, "Move journal",
            f"Move your journal to:\n{folder}\n\nYour entries are copied, checked, then removed from the old "
            "folder. This can take a moment, so keep the app open until it finishes.")
        if ok != QMessageBox.StandardButton.Yes:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            n = self.win.vault.move_to(folder)
        except (ValueError, OSError) as ex:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Couldn't move journal",
                                f"{ex}\n\nYour journal was not changed and is still at the old location.")
            return
        QApplication.restoreOverrideCursor()
        self.win.config.vault_path = self.win.vault.root
        self.win.config.save()
        self.on_show()
        QMessageBox.information(self, "Journal moved", f"Moved {n} {'entry' if n == 1 else 'entries'} to:\n"
                                f"{self.win.vault.root}")

    def set_theme(self, name: str) -> None:
        THEME.apply(name)
        self.win.config.theme = name
        self.win.config.save()
