# My Journal

A private diary for your computer. Write an entry each night, find old entries by date or tag, and keep everything locked behind a password. Your entries are encrypted on your own computer and are never sent anywhere.

Runs on Windows, macOS and Linux.

## Features

- **Write.** The date and time are filled in for you. Add a title and tags if you like, and format your text with bold, italic, headings and lists.
- **Find.** Browse your entries on a calendar, by tag, or all together.
- **Private.** Everything is encrypted with your password. The app never connects to the internet.
- **Recovery key.** A spare key that opens your journal if you forget your password.
- **Backup and restore.** Save your whole journal as one file, and bring entries back from it later. Backups stay encrypted. Find both in **Settings**.
- **Themes.** Light, Dark and Sepia.

> **Important:** nobody can reset your password. If you lose both your password and your recovery key, your entries are gone for good. Keep your recovery key somewhere safe, away from this computer.

## How to run it

### 1. Install Python (once)

- **Windows:** download Python from [python.org/downloads](https://www.python.org/downloads/) and run the installer. On the first screen, tick **Add python.exe to PATH**, then click **Install Now**.
- **macOS:** download Python from [python.org/downloads](https://www.python.org/downloads/) and run the installer.
- **Linux:** Python is usually installed already. On Debian or Ubuntu, also run `sudo apt install python3-venv`.

### 2. Download the app (once)

On this project's GitHub page, click the green **Code** button, then **Download ZIP**. Unzip it somewhere easy to find, such as your Documents folder.

### 3. Start the app

Open the unzipped folder, then:

| System | What to do |
|---|---|
| Windows | Double-click **run.bat** |
| macOS | Double-click **run.command** |
| Linux | Right-click **run.sh** and choose **Run as a Program** |

The first time, the app downloads what it needs (about 300 MB). This takes a few minutes. After that, it opens in a few seconds.

**Quicker next time**

- **Windows:** right-click **run.bat**, choose **Send to**, then **Desktop (create shortcut)**. On Windows 11, **Send to** is under **Show more options**.
- **macOS:** drag **run.command** to the right side of the Dock.
- **Linux:** My Journal is now in your applications menu, like any other app.

**If your computer warns you the first time**

- **Windows:** if you see "Windows protected your PC", click **More info**, then **Run anyway**.
- **macOS:** if it says **run.command** can't be opened, open **System Settings**, then **Privacy & Security**, scroll down, and click **Open Anyway**.
- **Linux:** if there is no **Run as a Program** option, right-click inside the folder, choose **Open in Terminal**, type `bash run.sh` and press Enter.

To remove the app, delete its folder (on Linux, also delete `my-journal.desktop` in `~/.local/share/applications`). Your journal is kept separately, so it stays safe.

### The first time you open it

1. Choose a password of at least 8 characters.
2. The app shows your **recovery key**. Copy it or write it down, keep it safe, then tick the box. It is shown only once.
3. Click **New entry** and start writing.

Your journal is saved in a folder called `JournalVault` in your home folder. You can move it in **Settings**, under **Storage**.

---

Developers and AI agents: see [AGENTS.md](AGENTS.md) for how the app works and how to contribute.
