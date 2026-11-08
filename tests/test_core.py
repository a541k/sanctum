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


# ---- restore from backups ---------------------------------------------------
import shutil
import journal_app.vault as vault_mod
from journal_app.vault import ENTRY_AAD

LATER = "2099-01-01T00:00:00+00:00"


def put_copy(vault, folder, e, name=None):
    """Write an encrypted copy of e, keeping its updated_at, the way a backup or a stray copy would hold it."""
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / (name or f"{e.id}.enc")
    p.write_bytes(crypto.encrypt(vault._key, e.to_bytes(), ENTRY_AAD))
    return p


def test_restore_adds_missing_and_keeps_newest(tmp_path):
    vault, _ = make(tmp_path)
    a = Entry.new(); a.content = "a"; vault.save_entry(a)
    b = Entry.new(); b.content = "b mine"; vault.save_entry(b)
    backup = tmp_path / "backup.zip"
    vault.export_backup(backup)
    vault.delete_entry(a.id)

    b2 = vault.get_entry(b.id); b2.content, b2.updated_at = "b edited elsewhere", LATER
    c = Entry.new(); c.content = "c"
    other = tmp_path / "other copy"
    put_copy(vault, other, b2, "renamed by drive (1).enc")
    put_copy(vault, other, c)

    plan = vault.scan_backups([backup, other])               # b is in both: the newest copy wins
    assert {e.id for e, _ in plan.new} == {a.id, c.id}
    assert [e.id for e, _ in plan.newer] == [b.id] and plan.same == 0 and plan.unreadable == 0
    assert vault.entry_count() == 1                           # scanning writes nothing
    assert vault.apply_import(plan) == 3
    assert [vault.get_entry(i).content for i in (a.id, b.id, c.id)] == ["a", "b edited elsewhere", "c"]
    assert len(list(vault.root.rglob("*.enc"))) == 3           # one file per entry, at its usual place

    old = vault.scan_backups([backup])                        # the old backup can't overwrite the newer edit
    assert old.same == 2 and not old.new and not old.newer
    vault.lock()
    v2 = Vault.open(tmp_path / "v", password="correct horse")
    assert v2.entry_count() == 3 and v2.get_entry(b.id).content == "b edited elsewhere" and not v2.load_errors


def test_restore_skips_other_journal_damaged_and_oversized(tmp_path, monkeypatch):
    vault, _ = make(tmp_path)
    other, _ = Vault.create(tmp_path / "other", "other password", kdf_n=FAST)
    other.save_entry(Entry.new()); other.save_entry(Entry.new())
    theirs = tmp_path / "theirs.zip"
    other.export_backup(theirs)
    plan = vault.scan_backups([theirs])
    assert plan.found == 0 and plan.unreadable == 2

    junk = tmp_path / "junk"
    mine = put_copy(vault, junk, Entry.new())
    (junk / "fake.enc").write_bytes(b"x" * 100)
    (junk / "notes.txt").write_text("not an entry, ignored")
    (tmp_path / "broken.zip").write_bytes(b"not a zip")
    plan = vault.scan_backups([junk, tmp_path / "broken.zip"])
    assert len(plan.new) == 1 and plan.unreadable == 2

    z = tmp_path / "mine.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(mine, "entries/2026/x.enc")
    assert len(vault.scan_backups([z]).new) == 1
    monkeypatch.setattr(vault_mod, "MAX_IMPORT_FILE_SIZE", 10)   # zip-bomb guard: oversized members are skipped
    assert vault.scan_backups([z]).unreadable == 1 and vault.scan_backups([junk]).unreadable == 2
    monkeypatch.setattr(vault_mod, "MAX_IMPORT_FILES", 1)
    with pytest.raises(ValueError):
        vault.scan_backups([junk])
    monkeypatch.setattr(vault_mod, "MAX_IMPORT_FILES", 100)
    monkeypatch.setattr(vault_mod, "MAX_IMPORT_FILE_SIZE", 1_000_000)
    monkeypatch.setattr(vault_mod, "MAX_IMPORT_BYTES", len(mine.read_bytes()))
    with pytest.raises(ValueError):                              # total size limit
        vault.scan_backups([junk])
    assert vault.entry_count() == 0


def test_restore_survives_zip_bomb_with_lying_header(tmp_path, monkeypatch):
    import struct, tracemalloc
    vault, _ = make(tmp_path)
    bomb = tmp_path / "bomb.zip"
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("entries/2026/x.enc", b"\0" * 20_000_000)      # 20 MB that compresses to ~20 KB
    data = bytearray(bomb.read_bytes())                            # claim it unpacks to only 100 bytes
    struct.pack_into("<I", data, data.find(b"PK\x03\x04") + 22, 100)
    struct.pack_into("<I", data, data.find(b"PK\x01\x02") + 24, 100)
    bomb.write_bytes(bytes(data))
    monkeypatch.setattr(vault_mod, "MAX_IMPORT_FILE_SIZE", 1_000_000)
    tracemalloc.start()
    try:
        plan = vault.scan_backups([bomb])
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert plan.unreadable == 1 and not plan.new
    assert peak < 5_000_000                                         # never unpacked the 20 MB


@pytest.mark.parametrize("folder", ["0", "zz"])  # the newer copy is read before / after the usual file
def test_duplicate_copies_keep_newest_and_delete_removes_all(tmp_path, folder):
    vault, _ = make(tmp_path)
    e = vault.save_entry(Entry.new())
    e.content, e.updated_at = "newest", LATER
    put_copy(vault, vault.root / "entries" / folder, e, "pasted (1).enc")
    vault.lock()
    v2 = Vault.open(tmp_path / "v", password="correct horse")
    assert v2.entry_count() == 1 and v2.get_entry(e.id).content == "newest"
    v2.delete_entry(e.id)
    assert not list(v2.root.rglob("*.enc"))
    v2.lock()
    assert Vault.open(tmp_path / "v", password="correct horse").entry_count() == 0  # doesn't come back


def test_saving_tidies_duplicate_copies(tmp_path):
    vault, _ = make(tmp_path)
    e = vault.save_entry(Entry.new())
    shutil.copy(vault._entry_path(e), vault.root / "entries" / "pasted (1).enc")
    vault.lock()
    v2 = Vault.open(tmp_path / "v", password="correct horse")
    assert len(list(v2.root.rglob("*.enc"))) == 2
    v2.save_entry(v2.get_entry(e.id))
    assert [p.name for p in v2.root.rglob("*.enc")] == [v2._entry_path(e).name]
