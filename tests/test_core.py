import pytest

from journal_app import crypto
from journal_app.vault import Entry, InvalidCredentials, Vault, parse_tag_string

FAST = 2**10  # cheap scrypt for tests


def make(tmp_path):
    return Vault.create(tmp_path / "v", "correct horse", kdf_n=FAST)


def test_roundtrip_and_unlock(tmp_path):
    vault, _ = make(tmp_path)
    e = Entry.new()
    e.title, e.content, e.tags = "Hello", "**bold** text — ünïcode", ["Work", "#Life"]
    vault.save_entry(e)
    vault.lock()

    v2 = Vault.open(tmp_path / "v", password="correct horse")
    got = v2.get_entry(e.id)
    assert got.title == "Hello"
    assert got.content == "**bold** text — ünïcode"
    assert got.tags == ["work", "life"]


def test_wrong_password(tmp_path):
    make(tmp_path)[0].lock()
    with pytest.raises(InvalidCredentials):
        Vault.open(tmp_path / "v", password="nope")


def test_recovery_key_and_change_password(tmp_path):
    vault, rec = make(tmp_path)
    e = vault.save_entry(Entry.new())
    vault.lock()

    v2 = Vault.open(tmp_path / "v", recovery_key=rec.lower())
    v2.change_password("new password", kdf_n=FAST)
    v2.lock()

    with pytest.raises(InvalidCredentials):
        Vault.open(tmp_path / "v", password="correct horse")
    v3 = Vault.open(tmp_path / "v", password="new password")
    assert v3.get_entry(e.id).id == e.id


def test_nothing_readable_on_disk(tmp_path):
    vault, _ = make(tmp_path)
    e = Entry.new()
    e.title, e.content = "SECRET-TITLE", "SECRET-BODY"
    vault.save_entry(e)
    for p in (tmp_path / "v").rglob("*"):
        if p.is_file():
            data = p.read_bytes()
            assert b"SECRET" not in data


def test_tamper_detected(tmp_path):
    vault, _ = make(tmp_path)
    e = vault.save_entry(Entry.new())
    f = next((tmp_path / "v" / "entries").rglob("*.enc"))
    raw = bytearray(f.read_bytes())
    raw[-1] ^= 1
    f.write_bytes(bytes(raw))
    vault.lock()
    v2 = Vault.open(tmp_path / "v", password="correct horse")
    assert len(v2.load_errors) == 1
    assert v2.all_entries() == []


def test_queries(tmp_path):
    vault, _ = make(tmp_path)
    a, b = Entry.new(), Entry.new()
    a.created_at = "2026-11-04T22:31:05+06:00"
    b.created_at = "2026-11-05T08:00:00+06:00"
    a.tags, b.tags = ["gym", "life"], ["life"]
    vault.save_entry(a)
    vault.save_entry(b)
    assert vault.dates_in_month(2026, 11) == {"2026-11-04", "2026-11-05"}
    assert vault.dates_in_month(2026, 10) == set()
    assert [s.id for s in vault.entries_for_date("2026-11-04")] == [a.id]
    assert {s.id for s in vault.entries_for_tag("life")} == {a.id, b.id}
    assert vault.all_tags() == [("gym", 1), ("life", 2)]
    vault.delete_entry(a.id)
    assert vault.all_tags() == [("life", 1)]
    assert vault.entries_for_date("2026-11-04") == []


def test_tag_parsing():
    assert parse_tag_string("Work, #life; work , ") == ["work", "life"]


def test_recovery_key_format():
    raw, text = crypto.generate_recovery_key()
    assert crypto.parse_recovery_key(text) == raw


# ---- new in the home-menu version -------------------------------------------
import zipfile
from journal_app.config import Config
from journal_app.vault import make_preview


def test_preview_strips_markdown():
    md = "# Evening\n\nWent for a **long** walk\n\n- bread\n- milk"
    assert make_preview(md) == "Evening. Went for a long walk. bread. milk."
    assert make_preview("x" * 300).endswith("…")


def test_verify_password_and_counts(tmp_path):
    vault, _ = make(tmp_path)
    assert vault.verify_password("correct horse") and not vault.verify_password("nope")
    assert vault.entry_count() == 0 and vault.latest_date() is None
    e = Entry.new(); e.content = "hello world"; vault.save_entry(e)
    assert vault.entry_count() == 1 and vault.latest_date() == e.date
    assert vault.all_entries()[0].preview == "hello world."


def test_export_backup_is_encrypted_and_restorable(tmp_path):
    vault, _ = make(tmp_path)
    e = Entry.new(); e.title = "SECRET"; e.content = "SECRET-BODY"; vault.save_entry(e)
    out = tmp_path / "backup.zip"
    assert vault.export_backup(out) == 1
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "vault.json" in names and sum(n.endswith(".enc") for n in names) == 1
        assert all(b"SECRET" not in z.read(n) for n in names)
        z.extractall(tmp_path / "restored")
    restored = Vault.open(tmp_path / "restored", password="correct horse")
    assert restored.get_entry(e.id).content == "SECRET-BODY"


def test_move_vault(tmp_path):
    vault, _ = make(tmp_path)
    ids = [vault.save_entry(Entry.new()).id for _ in range(3)]
    old = vault.root
    assert vault.move_to(tmp_path / "new" / "place") == 3
    assert not (old / "vault.json").exists() and not list(old.glob("entries/**/*.enc"))
    assert vault.get_entry(ids[0]).id == ids[0]               # still works after the move
    vault.save_entry(Entry.new())                              # and writes to the new place
    assert len(list((tmp_path / "new" / "place").glob("entries/**/*.enc"))) == 4
    Vault.open(tmp_path / "new" / "place", password="correct horse").lock()


def test_move_vault_rejects_bad_targets(tmp_path):
    vault, _ = make(tmp_path)
    vault.save_entry(Entry.new())
    (tmp_path / "full").mkdir(); (tmp_path / "full" / "x.txt").write_text("hi")
    for bad in (vault.root, vault.root / "entries", tmp_path / "full", tmp_path):
        with pytest.raises(ValueError):
            vault.move_to(bad)
    assert vault.entry_count() == 1 and (vault.root / "vault.json").exists()


def test_config_roundtrip(tmp_path):
    c = Config(tmp_path / "c.json")
    assert c.theme == "light"
    c.theme, c.vault_path = "dark", tmp_path / "vv"
    c.save()
    c2 = Config(tmp_path / "c.json")
    assert c2.theme == "dark" and c2.vault_path == tmp_path / "vv"
    (tmp_path / "bad.json").write_text("{not json")
    assert Config(tmp_path / "bad.json").theme == "light"        # corrupt file falls back to defaults
