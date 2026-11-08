# AGENTS.md: how My Journal works

Context for developers and AI agents who change this code. The user-facing README stays short on purpose. Put technical detail here instead.

## 1. What it is

A single-user, offline, encrypted desktop journal.

| | |
|---|---|
| Language | Python 3.9+ (3.8 does **not** work: `crypto.py` uses `tuple[...]` at runtime) |
| UI | PySide6 (Qt 6), Fusion style, one global stylesheet |
| Crypto | `cryptography`: AES-256-GCM and scrypt |
| Storage | One encrypted file per entry, plus `vault.json`. An in-memory SQLite index while unlocked |
| Network | None. Any network feature must be opt-in and called out in the README |

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # dev setup (Windows: .venv\Scripts\pip)
python -m journal_app [--vault PATH]   # --vault is resolved and saved to the config (it persists)
python -m pytest                       # UI tests set QT_QPA_PLATFORM=offscreen themselves
```

End users never type these. They double-click a launcher (§7).

## 2. Layout and dependency rule

```
journal_app/
  __main__.py     argparse → Config → QApplication → THEME → authenticate() → MainWindow
  crypto.py       AES-GCM encrypt/decrypt, scrypt, recovery key format         ┐ core: must never
  vault.py        Vault: create/open, entries, index, backup, restore, move    │ import Qt
  config.py       Preferences JSON (no secrets)                                ┘
  theme.py        Palettes, QSS template, fonts, ThemeManager (THEME), bind_icon
  icons.py        SVG line icons, rendered in a theme colour
  widgets.py      make_label/make_button helpers, Tile, EntryCard, EntryList, CalendarWidget
  editor.py       EntryEditor: the "paper" page and formatting toolbar
  dialogs.py      NewPasswordDialog, RecoveryKeyDialog, UnlockDialog, authenticate()
  pages.py        Page base, HomePage, BrowsePage, EntryPage, SettingsPage
  main_window.py  Top bar, page stack, navigation history, lock
tests/
  test_core.py    crypto/vault/config tests, no Qt
  test_ui.py      offscreen Qt tests: navigation, dialogs, settings actions
run.bat           Windows launcher (double-click)                        ┐
run.command       macOS launcher (double-click), just runs run.sh        │ see §7
run.sh            Linux launcher, plus the shared Linux/macOS logic      ┘
.gitattributes    keeps CRLF in .bat, LF in .sh/.command
README.md         for end users only: features + how to run. Keep it short
AGENTS.md         this file.  CLAUDE.md just imports it
```

UI → core only. `crypto.py`, `vault.py` and `config.py` must stay free of Qt, so a web or mobile version can reuse the format.

## 3. Security model

### Keys

```
password ──scrypt(salt, n=2^15, r=8, p=1)──► pw_key ──AES-GCM wrap──┐
                                                                    ├──► master key (random 32 bytes)
recovery key (random 32 bytes) ─────────────────────AES-GCM wrap────┘          │
                                                                        AES-GCM encrypts
                                                                               ▼
                                                                    entries/YYYY/*.enc
```

- The **master key never changes**. Every backup of a journal uses the same master key.
- **Change password** = new salt + re-wrap the master key in `vault.json`. Entry files are untouched.
- The **recovery key never changes** (no rotation yet). It opens every backup ever made.
- AES-GCM uses a random 12-byte nonce per encryption. Encrypting the same plaintext twice gives **different bytes**, so never compare entries by file hash. Decrypt and compare `updated_at`.
- AES-GCM authentication means a file that was changed, or encrypted with another journal's key, fails to decrypt. Treat that as "damaged or not ours" and skip it.

### On disk

```
<vault>/
  vault.json
  entries/YYYY/YYYY-MM-DD_HHMMSS_<id[:8]>.enc
```

`vault.json` (plain JSON, holds no secrets in clear):

```json
{
  "format": 1,
  "kdf": {"name": "scrypt", "n": 32768, "r": 8, "p": 1, "salt": "<base64, 16 bytes>"},
  "wrapped_key": "<base64: AES-GCM(pw_key, master, aad=journal-master-key-v1)>",
  "recovery_wrapped_key": "<base64: AES-GCM(recovery_raw, master, aad=journal-master-key-v1)>"
}
```

Entry file = `nonce (12) || ciphertext || tag (16)`, AAD `journal-entry-v1`. The plaintext is UTF-8 JSON:

| Field | Notes |
|---|---|
| `id` | `uuid4().hex`. The real identity of an entry (file names are only a hint) |
| `created_at` | ISO 8601, local time with offset, whole seconds. Fixes the file path for the entry's whole life |
| `updated_at` | Same format. Set on every save. Decides "newer" in restore and duplicates |
| `title`, `tags` | Tags are normalised: lowercase, no `#`, unique, order kept (`normalize_tags`) |
| `content` | Markdown, produced by `QTextDocument.toMarkdown()` |
| `attachments` | Reserved, always `[]` |
| `version` | `1` |

Recovery key text: 32 random bytes → base32 without padding → groups of 4 joined by `-`. Parsing ignores spaces, dashes and case.

### Rules that must hold

- **Never write plaintext to disk.** Titles, tags and text live only inside `.enc` files and in memory.
- **Write atomically.** Use `_write_atomic` (temp file + `os.replace`). `Config.save` does the same.
- **Only touch files the app owns.** `_vault_files()` = `vault.json` + `entries/**/*.enc`. Never delete anything else in a folder.
- File names reveal *when* entries were written. That is accepted and documented.
- While unlocked, entries are decrypted in memory. There is no auto-lock yet.
- The app has not had an independent security audit.

## 4. Vault internals (`vault.py`)

### Opening

`Vault.open(root, password=... | recovery_key=...)` unwraps the master key, or raises `InvalidCredentials`. Then `_load_index()` decrypts every `.enc` file into an in-memory SQLite database:

```sql
entries(id PK, path, created_at, updated_at, date, title, tags /*json*/, preview)
tags(entry_id, tag)
```

- `path` is **relative** to the vault root (posix style). That keeps the index valid after `move_to`.
- A file that fails to decrypt goes into `vault.load_errors`. `MainWindow` shows a warning, and the rest still loads.
- **Same id in several files** (for example, copied in by hand): the newest `updated_at` is indexed. Older copies are remembered in `self._extra` (relative paths).

### Writing

All entry writes go through `_put(entry, blob)`: write the canonical path atomically → re-index → delete older copies (the previous path plus `_extra`). `save_entry` encrypts and calls `_put`. `delete_entry` removes the indexed file **and** every `_extra` copy, so a deleted entry can't come back on the next unlock.

### Reading

The UI reads only from the index: `dates_in_month`, `entries_for_date`, `entries_for_tag`, `all_entries`, `all_tags`, `entry_count`, `latest_date`. These return `Summary(id, created_at, title, tags, preview)`. `get_entry(id)` decrypts one file. `make_preview` strips Markdown and cuts the text at 160 characters.

### Locking

`lock()` sets the key to `None` and **closes the database**. After that, the Vault object is dead. `authenticate()` builds a new one. Any UI code that runs after `lock()` must not touch the vault (see §6, Lock).

### Backup (export)

`export_backup(dest)` writes a ZIP (stored, no compression, because the data is already encrypted) of `_vault_files()`, atomically, and returns the entry count. The UI suggests `journal-backup-YYYY-MM-DD_HHMM.zip` next to the vault folder, so a new backup never replaces an old one. Backups are manual for now: the person uploads the file wherever they like (for example Google Drive).

### Restore (import)

Two steps, so the UI can show a summary first:

1. `scan_backups(sources) -> ImportPlan` writes nothing. Sources can be ZIPs, folders (searched recursively) or loose `.enc` files. Every `.enc` is decrypted with **this** journal's key, whatever its name. The plan has `new`, `newer` (lists of `(Entry, blob)`), `same` and `unreadable` (counts).
2. `apply_import(plan)` copies each winning blob **byte for byte** with `_put`. No re-encryption is needed, because the key is the same. It re-checks "still newer" before writing.

Rules: add what's missing. When the same id appears in several places, keep the newest `updated_at`. Never delete. Compare `datetime` objects, not strings (offsets can differ).

Guards against hostile files:
- ZIPs are read in memory and never extracted, so there is no zip-slip.
- Each member is read with `z.open(info).read(MAX_IMPORT_FILE_SIZE + 1)`. **Never use `z.read(info)`**: it trusts the size in the ZIP header, so a 200 KB zip that lies about its size can unpack hundreds of MB before the CRC check fails (tested: 449 MB peak). Anything over `MAX_IMPORT_FILE_SIZE` (50 MB) counts as unreadable.
- More than `MAX_IMPORT_FILES` (100,000) files, or more than `MAX_IMPORT_BYTES` (2 GB) in total, raises `ValueError` and nothing is written.
- `test_restore_survives_zip_bomb_with_lying_header` measures peak memory to keep this honest.

Accepted limits:
- Deleted entries come back if a backup has them (no tombstones).
- An entry edited in two copies keeps only the newer edit (no version history).
- Another journal's files are skipped, not imported.
- `updated_at` has 1-second resolution.

### Move

`move_to(new_root)` refuses the same folder, nested folders and non-empty folders. Then: copy → verify with SHA-256 → switch `self.root` → delete the old files and empty folders. On any failure it cleans up the new folder and raises. The original stays untouched.

## 5. Config (`config.py`)

`%APPDATA%\EncryptedJournal\config.json` on Windows, otherwise `$XDG_CONFIG_HOME` or `~/.config/EncryptedJournal/config.json`. Keys: `vault_path` (default `~/JournalVault`), `theme`, `last_backup`. **No secrets here, ever.** A corrupt file falls back to defaults. `last_backup` is a display string, not a timestamp (a known wart).

## 6. UI architecture

### Pages and navigation

- `MainWindow` holds one instance of each page in a `QStackedWidget`: `home`, `browse`, `entry`, `settings`.
- `Page` has two hooks:
  - `on_show()` runs **every time** the page is shown. Refresh data from the vault here.
  - `can_leave() -> bool` is asked before navigating away. `EntryPage` offers Save / Discard / Cancel for unsaved edits.
- `navigate(page, push=True)` checks `can_leave`, pushes history, switches page, calls `on_show`. `go_back()` and `go_home()` sit on top of it.
- To open things, use `win.new_entry()`, `win.open_entry(id)`, `win.show_browse(tab)` and `win.show_settings()`.
- Shortcuts: `Ctrl+N` new, `Ctrl+S` save, `Ctrl+L` lock, `Alt+Left` back. The editor adds `Ctrl+B` and `Ctrl+I`.

### Sign-in

`authenticate(root)`:
- If there is no `vault.json`: `NewPasswordDialog` → `Vault.create` → `RecoveryKeyDialog`. Esc can't skip that dialog, and Done stays disabled until the box is ticked.
- Otherwise: `UnlockDialog` (password, or recovery key). After a recovery-key unlock, it asks for a new password.
- Minimum password length is 8 (`MIN_PASSWORD_LEN`). scrypt runs on the UI thread, which takes a fraction of a second.

### Lock (order matters)

```
can_leave? → clear editor → clear history → navigate(home)   ← vault must still be open: Home.on_show reads it
           → vault.lock() → hide() → authenticate() → new vault + navigate(home) + show()   (or quit on cancel)
```

`app.setQuitOnLastWindowClosed(False)` lets Lock hide the window without quitting. `closeEvent` quits explicitly.

### Editor

`QTextEdit` with `setAcceptRichText(False)`: pasted text arrives plain, and formatting comes only from the toolbar. Bold, italic and strike use char formats. H1/H2 set the block heading level plus the font size (`HEADING_PT`). Lists use `QTextListFormat`. The content is loaded with `setMarkdown` and saved with `toMarkdown`. `dirty` tracking is suppressed while loading (`_loading`).

### Theme and widgets

- `PALETTES` holds `light`, `dark` and `sepia`. Tokens: `bg surface surface_alt border ink muted faint accent accent_ink accent_soft hover danger` (+ `label`).
- `QSS` is a template using `@token` (and `@serif`, `@sans`). `build_qss` replaces the longest names first, so `@surface_alt` is replaced before `@surface`.
- Widgets are styled with **dynamic properties**, not object names: `role="h1"`, `role="primary"`, `card="true"`, `paper="true"`, `bare="title"`, `cal="day"`, `tone="onaccent"`. If you change a property at runtime, call `repolish(widget)`.
- `THEME` is a singleton. `THEME.apply(name)` sets the palette and stylesheet and emits `changed`. `bind_icon(widget, name, color_key, size)` keeps icons in the theme colour.
- Helpers: `make_label(text, role, wrap)`, `make_button(text, role, icon, icon_color)`, `centered(widget, max_width)`, `make_scroll`, `card_frame`, `divider`.
- The calendar starts weeks on Sunday and always shows 6 rows. Days with entries get the `entry="true"` property.

## 7. Launchers (`run.bat`, `run.command`, `run.sh`)

They let people with no tech knowledge start the app by double-clicking. They all follow the same steps:

```
find Python ≥ 3.9 ──none──► friendly message + python.org link, then stop
      │
make .venv next to the launcher (first run only; a failed attempt is deleted)
      │
requirements.txt differs from .venv/requirements.installed? ──yes──► pip install, then copy the file
      │
start the app detached (closing the window doesn't close the app)
```

| | Windows `run.bat` | Linux / macOS `run.sh` |
|---|---|---|
| Finds Python | `py -3`, then `python` | `python3`, then `python` |
| Starts the app | `pythonw.exe` (no console window). No feedback if it crashes later | `nohup … > .venv/app.log`, then waits 3 s. If the app died with an error, it prints the log. The missing `libxcb-cursor0` (Qt 6.5+ on Linux) gets its own message |
| No terminal visible | n/a (always a console) | Messages also go to `notify-send` if it exists (for example when started from the menu or a file manager) |
| Extra | | Linux: writes `~/.local/share/applications/my-journal.desktop` (`Exec=bash "<folder>/run.sh"`) on every run, so the menu entry follows the folder |

Rules:
- `run.bat` must keep **CRLF** line endings (`.gitattributes` handles this). `run.sh` and `run.command` must keep **LF** and the executable bit (git mode `100755`).
- All user-facing text in the launchers follows §9: plain sentences that say what to do next.
- **Adding a dependency:** add it to `requirements.txt`. Launchers reinstall automatically on the next start, because the file no longer matches the copy in `.venv`.
- **Tested:** `run.sh` on Linux (Ubuntu 20.04 with Python 3.12): Python too old, first run, second run (about 3 s), crash at start, and a valid menu entry (`desktop-file-validate`). `run.bat` and `run.command` have **not** been tried on real Windows or macOS yet.

## 8. How to add things

- **Home menu option:** add a `Tile(icon, title, subtitle)` in `HomePage.__init__`, plus a matching `show_…` method on `MainWindow`.
- **Setting:** `section.add_row(title, description, *buttons)` in `SettingsPage.__init__`, plus a method for the action.
- **Page:** subclass `Page`, add it to the stack in `MainWindow.__init__`, and open it with `win.navigate(page)`.
- **Icon:** add an SVG path (24×24, stroke) to `icons.PATHS`.
- **Vault feature:** put the logic in `vault.py` with no Qt, test it in `test_core.py`, then wire up the UI and test it in `test_ui.py`.

## 9. Conventions

- **Code:** short and direct. `from __future__ import annotations` and type hints. Comments explain *why*. Sections are marked with `# ---- name ----`. Match the style of the surrounding code.
- **User-facing text:** plain, short sentences that speak to the person ("your journal", "entry", "backup"). No jargon. Say what will happen and what won't ("Nothing in your journal is deleted."). Get plurals right (`_entries(n)` in `pages.py`).
- **Confirmations:** wrap a dialog in a small method (`_confirm_delete`, `_confirm_restore`) so tests can monkeypatch it.
- **Long actions:** use a wait cursor (`QApplication.setOverrideCursor`), and always restore it on every path.
- **Errors:** turn expected failures (`ValueError`, `OSError`) into a friendly `QMessageBox`. Say whether anything changed.

## 10. Tests

- Core tests create vaults with `kdf_n=2**10` (`FAST`), which keeps scrypt cheap.
- UI tests use the `win` fixture (a real `MainWindow` on a temp vault). Monkeypatch `QFileDialog.*`, `QMessageBox.*` and `_confirm_*`. Never let a real modal dialog open.
- To write a backup copy with a chosen `updated_at`, use the `put_copy()` helper in `test_core.py`.
- Every change needs tests. A bug fix should come with a test that fails without the fix.

## 11. Decisions and roadmap

Already decided:
- **Backups are manual:** export a ZIP, and the person keeps or uploads it.
- **Restore is the simple merge** in §4: add missing entries, keep the newest, never delete.

Planned or discussed, **not built**:

| Item | Notes |
|---|---|
| Google Drive backup | Direct Drive API, `drive.file` scope (non-sensitive: the app sees only files it created). Mirror the same encrypted files into a visible folder. OAuth for desktop apps with loopback + PKCE. Store the refresh token encrypted or in the OS keyring, never in `config.json`. Run network calls in a background thread. Opt-in, and update the README's privacy promise. No server of ours |
| Smarter merge | `vault_id` in `vault.json`, earlier-version stamps per entry, an encrypted `deleted.enc` list (tombstones). These fix deleted entries coming back and edits made in two places |
| Security | Raise scrypt cost (OWASP suggests n=2^17) and push for longer passphrases before any cloud feature. Add a way to rotate the recovery key |
| Features | Auto-lock after inactivity, search inside entry text, photo attachments, a packaged double-click app |

Known issues:
- After Lock, the Browse lists keep titles and previews in widget memory until the next unlock.
- `last_backup` is a display string.
