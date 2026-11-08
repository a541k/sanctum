import os
import re
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from PySide6.QtGui import QTextListFormat

from journal_app.config import Config
from journal_app.dialogs import NewPasswordDialog, RecoveryKeyDialog, UnlockDialog
from journal_app.main_window import MainWindow
from journal_app.theme import PALETTES, THEME
from journal_app.vault import Entry, Vault


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    THEME.init_fonts(); THEME.apply("light")
    return a


@pytest.fixture
def win(app, tmp_path):
    vault, _ = Vault.create(tmp_path / "v", "password123", kdf_n=2**10)
    cfg = Config(tmp_path / "cfg.json"); cfg.vault_path = tmp_path / "v"
    w = MainWindow(vault, cfg)
    yield w
    w.entry.editor.dirty = False


def test_starts_on_home_without_back(win):
    assert win.current is win.home
    assert win.back_btn.isHidden() and win.home_btn.isHidden()


def test_write_save_and_browse(win):
    win.new_entry()
    assert win.current is win.entry and not win.back_btn.isHidden()
    ed = win.entry.editor
    assert ed.date_label.text() and ed.time_label.text()          # auto date/time
    ed.title.setText("First night"); ed.tags.setText("Life, reflection")
    ed.text.setPlainText("Heading\nbody text\nitem one\nitem two")
    doc = ed.text.document(); cur = ed.text.textCursor()
    cur.setPosition(0); ed.text.setTextCursor(cur); ed.set_heading(1)
    for i in (2, 3):
        cur.setPosition(doc.findBlockByNumber(i).position()); ed.text.setTextCursor(cur)
        ed.toggle_list(QTextListFormat.Style.ListDisc)
    cur.setPosition(doc.findBlockByNumber(1).position())
    cur.movePosition(cur.MoveOperation.EndOfBlock, cur.MoveMode.KeepAnchor)
    ed.text.setTextCursor(cur); ed.toggle_bold()
    assert ed.dirty
    win.entry.save()
    assert not ed.dirty
    md = win.vault.get_entry(ed.entry.id).content
    assert md.startswith("# Heading") and "**body text**" in md and "- item one" in md

    # home shows the count
    win.go_home()
    assert "1 entry" in win.home.stats.text()
    # browse by date: calendar marks today, list has the card
    win.show_browse(0)
    assert win.browse.day_list.vbox.count() == 2                   # one card + stretch
    today_cells = [b for row in win.browse.calendar.cells for b in row if b.property("today") == "true"]
    assert today_cells and today_cells[0].property("entry") == "true"
    # browse by tag
    win.browse.show_tab(1)
    assert win.browse.tag_list.count() == 2
    win.browse._show_tag("life")
    assert win.browse.tag_title.text() == "#life"
    # open from list, back returns to browse
    win.open_entry(ed.entry.id)
    assert win.current is win.entry and "body text" in ed.text.toPlainText()
    win.go_back()
    assert win.current is win.browse


def test_unsaved_changes_block_navigation(win, monkeypatch):
    win.new_entry()
    win.entry.editor.text.setPlainText("draft")
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Cancel)
    win.go_home()
    assert win.current is win.entry                               # stayed
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Discard)
    win.go_home()
    assert win.current is win.home and win.vault.entry_count() == 0


def test_delete_entry_returns_to_previous_page(win, monkeypatch):
    e = win.vault.save_entry(Entry.new())
    win.show_browse(2)
    win.open_entry(e.id)
    monkeypatch.setattr(win.entry, "_confirm_delete", lambda: True)
    win.entry.delete()
    assert win.vault.entry_count() == 0 and win.current is win.browse


def test_theme_switch_persists(win):
    win.show_settings()
    for name in PALETTES:
        win.settings.theme_buttons[name].click()
        assert THEME.name == name and win.config.theme == name
        assert Config(win.config.path).theme == name
    win.settings.theme_buttons["light"].click()


def test_settings_change_location(win, tmp_path, monkeypatch):
    from journal_app import pages
    win.vault.save_entry(Entry.new())
    new = tmp_path / "moved"
    monkeypatch.setattr(pages.QFileDialog, "getExistingDirectory", lambda *a, **k: str(new))
    monkeypatch.setattr(pages.QMessageBox, "question", lambda *a, **k: pages.QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(pages.QMessageBox, "information", lambda *a, **k: None)
    win.show_settings()
    win.settings.change_location()
    assert win.vault.root == new.resolve() and win.config.vault_path == new.resolve()
    assert Config(win.config.path).vault_path == new.resolve()
    assert win.vault.entry_count() == 1 and str(new.resolve()) in win.settings.path_desc.text()


def test_settings_export(win, tmp_path, monkeypatch):
    from journal_app import pages
    win.vault.save_entry(Entry.new())
    out = tmp_path / "b.zip"
    suggested = []
    monkeypatch.setattr(pages.QFileDialog, "getSaveFileName", lambda *a, **k: suggested.append(a[2]) or (str(out), ""))
    monkeypatch.setattr(pages.QMessageBox, "information", lambda *a, **k: None)
    win.show_settings(); win.settings.export_backup()
    assert out.exists() and "Last backup:" in win.settings.backup_desc.text()
    assert re.search(r"journal-backup-\d{4}-\d\d-\d\d_\d{4}\.zip$", suggested[0])   # date and time


def test_settings_restore(win, tmp_path, monkeypatch):
    from journal_app import pages
    e = win.vault.save_entry(Entry.new())
    out = tmp_path / "b.zip"
    win.vault.export_backup(out)
    win.vault.delete_entry(e.id)
    monkeypatch.setattr(pages.QFileDialog, "getOpenFileNames", lambda *a, **k: ([str(out)], ""))
    infos, asked = [], []
    monkeypatch.setattr(pages.QMessageBox, "information", lambda *a, **k: infos.append(a[2]))
    monkeypatch.setattr(win.settings, "_confirm_restore", lambda text: asked.append(text) or True)
    win.show_settings(); win.settings.restore_from_files()
    assert win.vault.entry_count() == 1 and "1 you don't have yet" in asked[0] and "Added 1 entry" in infos[-1]
    win.settings.restore_from_files()                                  # second time: nothing left to add
    assert len(asked) == 1 and "already in your journal" in infos[-1]


def test_lock_and_unlock(win, monkeypatch):
    from journal_app import main_window
    old = win.vault
    e = old.save_entry(Entry.new())
    win.show_browse(2); win.open_entry(e.id)
    monkeypatch.setattr(main_window, "authenticate", lambda root: Vault.open(root, password="password123"))
    win.lock()
    assert old._key is None and win.vault is not old and win.vault.entry_count() == 1
    assert win.current is win.home and not win.history and win.isVisible()


def test_lock_then_cancel_quits(win, monkeypatch):
    from journal_app import main_window
    quits = []
    monkeypatch.setattr(main_window, "authenticate", lambda root: None)
    monkeypatch.setattr(main_window.QApplication, "quit", lambda: quits.append(1))
    win.show(); win.lock()
    assert quits and win.vault._key is None and not win.isVisible()


# ---- dialogs -----------------------------------------------------------------
def test_recovery_dialog_closes(app):
    d = RecoveryKeyDialog("ABCD-EFGH")
    assert not d.done_btn.isEnabled()
    d.saved.setChecked(True); d.done_btn.click()
    assert d.result() == QDialog.DialogCode.Accepted


def test_new_password_dialog(app):
    d = NewPasswordDialog("t", "i")
    d.pw1.setText("short"); d.pw2.setText("short"); d._submit()
    assert d.result() != QDialog.DialogCode.Accepted
    d.pw1.setText("longenough1"); d.pw2.setText("different11"); d._submit()
    assert d.result() != QDialog.DialogCode.Accepted
    d.pw2.setText("longenough1"); d._submit()
    assert d.result() == QDialog.DialogCode.Accepted and d.password == "longenough1"


def test_change_password_requires_current(app):
    d = NewPasswordDialog("t", "i", verify=lambda p: p == "old-pass-1")
    d.current.setText("wrong"); d.pw1.setText("brandnew123"); d.pw2.setText("brandnew123"); d._submit()
    assert d.result() != QDialog.DialogCode.Accepted and "current" in d.error.text()
    d.current.setText("old-pass-1"); d._submit()
    assert d.result() == QDialog.DialogCode.Accepted


def test_unlock_dialog(app, tmp_path):
    v, rec = Vault.create(tmp_path / "v", "password123", kdf_n=2**10); v.lock()
    d = UnlockDialog(tmp_path / "v")
    d.field.setText("wrong"); d._attempt()
    assert d.vault is None and d.error.text()
    d.field.setText("password123"); d._attempt()
    assert d.vault is not None and d.result() == QDialog.DialogCode.Accepted
    d2 = UnlockDialog(tmp_path / "v"); d2._toggle_mode()
    d2.field.setText(rec); d2._attempt()
    assert d2.used_recovery and d2.vault is not None
