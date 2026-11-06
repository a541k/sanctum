"""Encrypted vault: entries on disk, searchable index in memory.

Layout on disk:
    <vault>/vault.json                      key-wrapping metadata (no secrets in clear)
    <vault>/entries/YYYY/<date>_<time>_<id>.enc   one encrypted file per entry

A random master key encrypts entries. The master key is stored twice, wrapped
(encrypted) by the password-derived key and by the recovery key. Changing the
password only re-wraps the master key; entries are untouched.

Note: filenames reveal *when* an entry was written, never what is in it.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import sqlite3
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from . import crypto

FORMAT_VERSION = 1
WRAP_AAD = b"journal-master-key-v1"
ENTRY_AAD = b"journal-entry-v1"


class InvalidCredentials(Exception):
    pass


class VaultExistsError(Exception):
    pass


def normalize_tags(tags) -> list[str]:
    out: list[str] = []
    for t in tags:
        t = t.strip().lstrip("#").strip().lower()
        if t and t not in out:
            out.append(t)
    return out


def parse_tag_string(text: str) -> list[str]:
    return normalize_tags(text.replace(";", ",").split(","))


@dataclass
class Entry:
    id: str
    created_at: str          # local time with UTC offset, ISO 8601
    updated_at: str
    title: str = ""
    tags: list[str] = field(default_factory=list)
    content: str = ""        # Markdown
    attachments: list[dict] = field(default_factory=list)  # reserved for later

    @staticmethod
    def new() -> "Entry":
        now = datetime.now().astimezone().replace(microsecond=0).isoformat()
        return Entry(id=uuid.uuid4().hex, created_at=now, updated_at=now)

    @property
    def created(self) -> datetime:
        return datetime.fromisoformat(self.created_at)

    @property
    def date(self) -> str:
        return self.created_at[:10]

    def to_bytes(self) -> bytes:
        d = asdict(self)
        d["version"] = FORMAT_VERSION
        return json.dumps(d, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def from_bytes(raw: bytes) -> "Entry":
        d = json.loads(raw.decode("utf-8"))
        d.pop("version", None)
        return Entry(**d)


class Summary(NamedTuple):
    id: str
    created_at: str
    title: str
    tags: list
    preview: str = ""

    @property
    def created(self) -> datetime:
        return datetime.fromisoformat(self.created_at)


SCHEMA = """
CREATE TABLE entries (id TEXT PRIMARY KEY, path TEXT, created_at TEXT, date TEXT,
                      title TEXT, tags TEXT, preview TEXT);
CREATE TABLE tags (entry_id TEXT, tag TEXT);
CREATE INDEX idx_date ON entries(date);
CREATE INDEX idx_tag ON tags(tag);
"""


_MD_LINE_PREFIX = re.compile(r"^\s*(#{1,6}\s+|[-*+]\s+|\d+\.\s+|>\s*)")


def make_preview(markdown: str, limit: int = 160) -> str:
    """Plain-text snippet of an entry, for list cards."""
    parts = []
    for ln in markdown.splitlines():
        ln = _MD_LINE_PREFIX.sub("", ln).replace("**", "").replace("__", "").replace("~~", "").replace("`", "").strip()
        if ln:
            parts.append(ln if ln[-1] in ".!?:;,…" else ln + ".")
    text = " ".join(" ".join(parts).split())
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class Vault:
    # ---- creation / opening ------------------------------------------------
    @staticmethod
    def exists(root) -> bool:
        return (Path(root) / "vault.json").is_file()

    @classmethod
    def create(cls, root, password: str, kdf_n: int = 2**15) -> tuple["Vault", str]:
        """Create a new vault. Returns (unlocked vault, recovery key string)."""
        root = Path(root)
        if cls.exists(root):
            raise VaultExistsError(str(root))
        master = crypto.new_key()
        salt = os.urandom(16)
        pw_key = crypto.derive_key(password, salt, n=kdf_n)
        rec_raw, rec_text = crypto.generate_recovery_key()
        meta = {
            "format": FORMAT_VERSION,
            "kdf": {"name": "scrypt", "n": kdf_n, "r": 8, "p": 1, "salt": _b64(salt)},
            "wrapped_key": _b64(crypto.encrypt(pw_key, master, WRAP_AAD)),
            "recovery_wrapped_key": _b64(crypto.encrypt(rec_raw, master, WRAP_AAD)),
        }
        (root / "entries").mkdir(parents=True, exist_ok=True)
        _write_atomic(root / "vault.json", json.dumps(meta, indent=2).encode())
        return cls(root, master, meta), rec_text

    @classmethod
    def open(cls, root, password: str | None = None, recovery_key: str | None = None) -> "Vault":
        root = Path(root)
        meta = json.loads((root / "vault.json").read_text())
        try:
            if recovery_key is not None:
                kek = crypto.parse_recovery_key(recovery_key)
                wrapped = meta["recovery_wrapped_key"]
            else:
                k = meta["kdf"]
                kek = crypto.derive_key(password or "", base64.b64decode(k["salt"]),
                                        n=k["n"], r=k["r"], p=k["p"])
                wrapped = meta["wrapped_key"]
            master = crypto.decrypt(kek, base64.b64decode(wrapped), WRAP_AAD)
        except crypto.DecryptionError:
            raise InvalidCredentials("Wrong password or recovery key")
        return cls(root, master, meta)

    def __init__(self, root: Path, master_key: bytes, meta: dict):
        self.root = Path(root)
        self._key: bytes | None = master_key
        self._meta = meta
        self.load_errors: list[str] = []
        self._db = sqlite3.connect(":memory:")
        self._db.executescript(SCHEMA)
        self._load_index()

    # ---- password management ----------------------------------------------
    def change_password(self, new_password: str, kdf_n: int | None = None) -> None:
        self._require_unlocked()
        n = kdf_n or self._meta["kdf"]["n"]
        salt = os.urandom(16)
        pw_key = crypto.derive_key(new_password, salt, n=n)
        self._meta["kdf"] = {"name": "scrypt", "n": n, "r": 8, "p": 1, "salt": _b64(salt)}
        self._meta["wrapped_key"] = _b64(crypto.encrypt(pw_key, self._key, WRAP_AAD))
        _write_atomic(self.root / "vault.json", json.dumps(self._meta, indent=2).encode())

    def lock(self) -> None:
        self._key = None
        self._db.close()

    def _require_unlocked(self) -> None:
        if self._key is None:
            raise RuntimeError("Vault is locked")

    # ---- entries ----------------------------------------------------------
    def _entry_path(self, e: Entry) -> Path:
        c = e.created
        name = f"{c:%Y-%m-%d}_{c:%H%M%S}_{e.id[:8]}.enc"
        return self.root / "entries" / f"{c:%Y}" / name

    def _index(self, e: Entry, path: Path) -> None:
        rel = path.relative_to(self.root).as_posix()
        self._db.execute("DELETE FROM entries WHERE id=?", (e.id,))
        self._db.execute("DELETE FROM tags WHERE entry_id=?", (e.id,))
        self._db.execute("INSERT INTO entries VALUES (?,?,?,?,?,?,?)",
                         (e.id, rel, e.created_at, e.date, e.title, json.dumps(e.tags),
                          make_preview(e.content)))
        self._db.executemany("INSERT INTO tags VALUES (?,?)", [(e.id, t) for t in e.tags])
        self._db.commit()

    def _load_index(self) -> None:
        for p in sorted((self.root / "entries").glob("**/*.enc")):
            try:
                e = Entry.from_bytes(crypto.decrypt(self._key, p.read_bytes(), ENTRY_AAD))
                self._index(e, p)
            except Exception as ex:  # corrupt file shouldn't block the whole journal
                self.load_errors.append(f"{p.name}: {ex}")

    def save_entry(self, e: Entry) -> Entry:
        self._require_unlocked()
        e.tags = normalize_tags(e.tags)
        e.updated_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
        path = self._entry_path(e)
        _write_atomic(path, crypto.encrypt(self._key, e.to_bytes(), ENTRY_AAD))
        self._index(e, path)
        return e

    def get_entry(self, entry_id: str) -> Entry:
        self._require_unlocked()
        row = self._db.execute("SELECT path FROM entries WHERE id=?", (entry_id,)).fetchone()
        if not row:
            raise KeyError(entry_id)
        blob = (self.root / row[0]).read_bytes()
        return Entry.from_bytes(crypto.decrypt(self._key, blob, ENTRY_AAD))

    def delete_entry(self, entry_id: str) -> None:
        self._require_unlocked()
        row = self._db.execute("SELECT path FROM entries WHERE id=?", (entry_id,)).fetchone()
        if row:
            (self.root / row[0]).unlink(missing_ok=True)
        self._db.execute("DELETE FROM entries WHERE id=?", (entry_id,))
        self._db.execute("DELETE FROM tags WHERE entry_id=?", (entry_id,))
        self._db.commit()

    # ---- queries (served from the in-memory index) ------------------------
    @staticmethod
    def _summaries(rows) -> list[Summary]:
        return [Summary(r[0], r[1], r[2], json.loads(r[3]), r[4]) for r in rows]

    def dates_in_month(self, year: int, month: int) -> set[str]:
        rows = self._db.execute("SELECT DISTINCT date FROM entries WHERE date LIKE ?",
                                (f"{year:04d}-{month:02d}-%",))
        return {r[0] for r in rows}

    def entries_for_date(self, date: str) -> list[Summary]:
        rows = self._db.execute(
            "SELECT id, created_at, title, tags, preview FROM entries WHERE date=? ORDER BY created_at", (date,))
        return self._summaries(rows)

    def entries_for_tag(self, tag: str) -> list[Summary]:
        rows = self._db.execute(
            "SELECT e.id, e.created_at, e.title, e.tags, e.preview FROM entries e "
            "JOIN tags t ON t.entry_id=e.id WHERE t.tag=? ORDER BY e.created_at DESC", (tag,))
        return self._summaries(rows)

    def all_entries(self) -> list[Summary]:
        rows = self._db.execute(
            "SELECT id, created_at, title, tags, preview FROM entries ORDER BY created_at DESC")
        return self._summaries(rows)

    def all_tags(self) -> list[tuple[str, int]]:
        rows = self._db.execute("SELECT tag, COUNT(*) FROM tags GROUP BY tag ORDER BY tag")
        return [(r[0], r[1]) for r in rows]

    def entry_count(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

    def latest_date(self) -> str | None:
        return self._db.execute("SELECT MAX(date) FROM entries").fetchone()[0]

    # ---- security / maintenance ------------------------------------------
    def verify_password(self, password: str) -> bool:
        k = self._meta["kdf"]
        try:
            kek = crypto.derive_key(password, base64.b64decode(k["salt"]), n=k["n"], r=k["r"], p=k["p"])
            crypto.decrypt(kek, base64.b64decode(self._meta["wrapped_key"]), WRAP_AAD)
            return True
        except crypto.DecryptionError:
            return False

    def _vault_files(self) -> list[Path]:
        """Only files this app owns: vault.json and the encrypted entries."""
        return [self.root / "vault.json"] + sorted((self.root / "entries").glob("**/*.enc"))

    def export_backup(self, dest) -> int:
        """Write a zip of the (still encrypted) vault. Returns the number of entries included."""
        self._require_unlocked()
        dest = Path(dest)
        tmp = dest.with_name(dest.name + ".tmp")
        files = self._vault_files()
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as z:  # data is already encrypted
            for f in files:
                z.write(f, arcname=f.relative_to(self.root).as_posix())
        os.replace(tmp, dest)
        return len(files) - 1

    def move_to(self, new_root) -> int:
        """Copy the vault to an empty folder, verify every file, switch over, then remove the old copy.

        Raises ValueError for an unsuitable folder and OSError if copying or verifying fails;
        in both cases the original vault is left untouched.
        """
        self._require_unlocked()
        old, new = self.root.resolve(), Path(new_root).resolve()
        if new == old:
            raise ValueError("That is already where your journal is stored.")
        if old in new.parents or new in old.parents:
            raise ValueError("Choose a folder that is not inside the current journal folder.")
        if new.exists() and any(new.iterdir()):
            raise ValueError("That folder isn't empty. Choose an empty folder or create a new one.")

        files = self._vault_files()
        existed = new.exists()
        new.mkdir(parents=True, exist_ok=True)
        try:
            for f in files:
                dest = new / f.relative_to(old)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
            for f in files:
                same = (hashlib.sha256(f.read_bytes()).digest()
                        == hashlib.sha256((new / f.relative_to(old)).read_bytes()).digest())
                if not same:
                    raise OSError(f"Verification failed for {f.name}")
        except Exception:
            if existed:
                for child in new.iterdir():
                    shutil.rmtree(child) if child.is_dir() else child.unlink()
            else:
                shutil.rmtree(new, ignore_errors=True)
            raise

        self.root = new  # index stores relative paths, so it stays valid
        for f in files:
            f.unlink(missing_ok=True)
        for d in sorted({f.parent for f in files}, key=lambda x: len(x.parts), reverse=True):
            try:
                d.rmdir()
            except OSError:
                pass
        return len(files) - 1
