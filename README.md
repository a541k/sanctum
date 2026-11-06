# My Journal

A private, encrypted desktop journal. Write an entry each night, browse your past entries by date or tag, and keep everything locked behind a password. Your entries are encrypted on your own computer, and nothing is sent anywhere.

Built with Python and PySide6 (Qt). Tested on Windows.

## Features

- **Write:** a diary-style page with the date and time filled in automatically, an optional title, optional tags, and a formatting toolbar (bold, italic, strikethrough, headings, bulleted and numbered lists).
- **Browse:** a month calendar where days with entries are highlighted, a tag list, and an "all entries" view. Entries appear as cards with a short preview.
- **Lock:** a password is required to open the journal. A recovery key is generated when you create it.
- **Back up:** export your whole journal as a `.zip` file. The backup stays encrypted.
- **Move:** relocate the journal to another folder from Settings. Files are copied and verified before the old copy is removed.
- **Themes:** Light, Dark and Sepia.

## Privacy and security

**How your data is protected**

- Every entry is stored as its own file, encrypted with **AES-256-GCM**. The encryption also detects tampering, so a modified or damaged file is reported and skipped.
- Your journal is encrypted with a random master key. That key is protected by your password through **scrypt** key derivation. The master key is also stored a second time, protected by your recovery key.
- Because only the master key depends on your password, changing your password is instant and doesn't touch your entries.
- Titles, tags and text are all inside the encrypted file. Nothing readable is written to disk, and the search index exists only in memory while the journal is unlocked.
- The app makes no network connections and collects no data.

**What to know before relying on it**

- **There is no password reset.** If you lose both your password and your recovery key, your entries cannot be recovered by anyone. Store the recovery key somewhere safe, away from this computer.
- **File names reveal timing.** An entry file is named like `2026-11-04_223105_ab12cd34.enc`, so someone with access to the folder can see when you wrote entries, but not what is in them.
- **While unlocked, your entries are decrypted in memory.** Use **Lock** when you step away. There is no automatic lock yet.
- **Bring-your-own backups.** The app does not upload your journal anywhere. Where you keep backups is up to you.
- This is a personal project. The encryption uses standard, widely reviewed components (the `cryptography` library), but the app itself has not had an independent security audit.

## Getting started

### Requirements

- Python 3.9 or newer (check with `python --version`)
- Windows, macOS or Linux

### Install and run

```powershell
# 1. Get the code
git clone https://github.com/YOUR-USERNAME/YOUR-REPO.git
cd YOUR-REPO

# 2. (Recommended) create an isolated environment
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the app
python -m journal_app           # on Windows you can also use: py -m journal_app
```

### First launch

1. Choose a password (at least 8 characters).
2. The app shows your **recovery key**. Write it down or copy it somewhere safe, then tick the box to continue. It is shown only once.
3. You land on the home screen. Choose **New entry** to start writing.

By default the journal is stored in a folder called `JournalVault` in your home directory (on Windows, `C:\Users\<you>\JournalVault`). To use a different folder:

```powershell
python -m journal_app --vault D:\MyJournal
```

The app remembers this choice. Your folder and theme are saved in a small settings file outside the journal (on Windows: `%APPDATA%\EncryptedJournal\config.json`). It contains no secrets.

## Using the app

| To do this | Go to |
|---|---|
| Write today's entry | Home, then **New entry** (or `Ctrl+N`) |
| Save an entry | **Save entry** (or `Ctrl+S`) |
| Find entries on a day | Home, then **By date**, then click a day |
| Find entries by topic | Home, then **By tag** |
| See everything | Home, then **All entries** |
| Change your password | Settings, then **Security** |
| Back up your journal | Settings, then **Backup**, then **Export** |
| Move the journal folder | Settings, then **Storage**, then **Change location** |
| Switch theme | Settings, then **Appearance** |
| Lock the journal | **Lock** in the top bar (or `Ctrl+L`) |

### Restoring from a backup

There is no restore button yet. To restore manually:

1. Extract the backup `.zip` into an **empty** folder.
2. Start the app pointing at that folder:
   ```powershell
   python -m journal_app --vault C:\path\to\extracted\folder
   ```
3. Unlock with the password (or recovery key) the journal had when the backup was made.

### Forgot your password?

On the unlock screen choose **Forgot your password? Use your recovery key**. After the key is accepted you will be asked to set a new password.

## Development

### Run the tests

```powershell
python -m pytest
```

The tests cover encryption, the vault, backup and moving, settings, navigation, and the dialogs. The interface tests run without a visible window.

### Project layout

```
journal_app/
  crypto.py        AES-256-GCM and scrypt helpers
  vault.py         vault, entries, in-memory search index, backup, move
  config.py        remembered preferences
  theme.py         palettes, fonts, stylesheet
  icons.py         line icons drawn in the theme colour
  widgets.py       calendar, entry cards, tiles, layout helpers
  editor.py        the diary page and formatting toolbar
  dialogs.py       create, unlock and password dialogs
  pages.py         Home, Browse, Entry and Settings pages
  main_window.py   top bar and page navigation
tests/             core and interface tests
```

The encryption and storage code (`crypto.py`, `vault.py`) does not depend on the interface, so it can be reused for a web or mobile version.

### Adding to the app

- **A new menu option on Home:** add a `Tile(...)` in `HomePage.__init__` and a matching `show_...` method on `MainWindow`.
- **A new setting:** add a row with `section.add_row(title, description, button)` in `SettingsPage`.
- **A new page:** subclass `Page`, add it to the stack in `MainWindow`, and open it with `win.navigate(page)`.

### Storage format

For anyone writing another reader for this format:

- `vault.json` holds the scrypt parameters and salt, plus the master key wrapped twice (by the password-derived key and by the recovery key).
- `entries/YYYY/<date>_<time>_<id>.enc` holds `nonce (12 bytes) || AES-256-GCM ciphertext and tag`, with the associated data `journal-entry-v1`.
- The decrypted entry is UTF-8 JSON: `id`, `created_at`, `updated_at`, `title`, `tags`, `content` (Markdown), `attachments` (reserved).

## Roadmap

- Automatic lock after inactivity
- Search inside entry text
- Google Drive backup and sync
- Photo attachments
- Restore from backup in the app
- Packaged app you can open with a double-click
