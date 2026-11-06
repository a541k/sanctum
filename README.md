# Personal Encrypted Journal

## Run
    pip install -r requirements.txt
    py -m journal_app                      # Windows
    python -m journal_app                  # macOS / Linux

First launch asks you to create a password and shows a one-time recovery key.
Your folder choice and theme are remembered (stored in %APPDATA%\EncryptedJournal\config.json).
`--vault <folder>` points the app at a different journal folder and remembers it.

## Screens
- Home: New entry, Browse (By date / By tag / All entries), Settings, Lock
- Settings: change password, export backup (.zip, still encrypted), move journal folder, theme

## Test
    python -m pytest

## Layout
    journal_app/crypto.py       AES-256-GCM + scrypt primitives
    journal_app/vault.py        vault, entries, in-memory search index, backup, move
    journal_app/config.py       remembered preferences
    journal_app/theme.py        palettes (Light / Dark / Sepia), fonts, stylesheet
    journal_app/icons.py        line icons drawn in the theme colour
    journal_app/widgets.py      calendar, entry cards, tiles, layout helpers
    journal_app/editor.py       the diary page + formatting toolbar
    journal_app/dialogs.py      create / unlock / password dialogs
    journal_app/pages.py        Home, Browse, Entry, Settings pages
    journal_app/main_window.py  top bar + page navigation

## Adding a setting or a menu option later
- New tile on Home: add a `Tile(...)` in `HomePage.__init__` and a `win.show_xxx()` method.
- New setting: add `section.add_row(title, description, button)` in `SettingsPage`.
- New page: subclass `Page`, add it to the stack in `MainWindow`, navigate with `win.navigate(page)`.

## Vault format (for future web/mobile ports)
- vault.json: scrypt params + salt, master key wrapped by password and by recovery key
- entries/YYYY/<date>_<time>_<id>.enc: nonce(12) || AES-256-GCM(ciphertext+tag), AAD "journal-entry-v1"
- entry plaintext: UTF-8 JSON {id, created_at, updated_at, title, tags, content(markdown), attachments}
