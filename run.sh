#!/usr/bin/env bash
# Starts My Journal on Linux and macOS (on macOS, double-click run.command, which calls this).
# The first run makes a private Python environment in .venv and downloads what the app needs.
set -u
cd "$(dirname "$0")" || exit 1
VENV=.venv

tell() {  # print, and show a desktop notification when there is no terminal to print to
    echo "$1"
    if [ ! -t 1 ] && command -v notify-send >/dev/null 2>&1; then notify-send "My Journal" "$1"; fi
}

fail() {
    echo
    tell "$1"
    echo
    if [ -t 0 ]; then read -r -p "Press Enter to close this window." _; fi
    exit 1
}

# 1. A private Python environment, made once
if [ ! -x "$VENV/bin/python" ]; then
    PY=""
    for p in python3 python; do
        if "$p" -c 'import sys; sys.exit(sys.version_info < (3, 9))' >/dev/null 2>&1; then PY=$p; break; fi
    done
    [ -n "$PY" ] || fail "My Journal needs Python 3.9 or newer. Get it from https://www.python.org/downloads/ (on Linux, from your software centre), then try again."
    tell "Setting up My Journal for the first time. This takes a few minutes..."
    if ! "$PY" -m venv "$VENV"; then
        rm -rf "$VENV"
        fail "Python couldn't make the app's environment. On Debian or Ubuntu, run:  sudo apt install python3-venv   then try again."
    fi
fi

# 2. What the app needs, installed again only when requirements.txt changes
if ! cmp -s requirements.txt "$VENV/requirements.installed"; then
    tell "Downloading what My Journal needs (about 300 MB). This takes a few minutes..."
    "$VENV/bin/python" -m pip install --disable-pip-version-check -r requirements.txt \
        || fail "Setup didn't finish. Check your internet connection and try again. If it keeps failing, delete the .venv folder and try again."
    cp requirements.txt "$VENV/requirements.installed"
fi

# 3. Linux: put My Journal in the applications menu. Rewritten on every run, so it follows the folder if moved.
if [ "$(uname)" = Linux ]; then
    entry="${XDG_DATA_HOME:-$HOME/.local/share}/applications/my-journal.desktop"
    [ -f "$entry" ] || new_entry=1
    mkdir -p "$(dirname "$entry")"
    cat >"$entry" <<EOF
[Desktop Entry]
Type=Application
Name=My Journal
Comment=Your private, encrypted journal
Exec=bash "$PWD/run.sh"
Icon=accessories-text-editor
Terminal=false
Categories=Utility;
EOF
    if [ -n "${new_entry:-}" ]; then tell "My Journal is now in your applications menu."; fi
fi

# 4. Start the app on its own, so closing this window doesn't close it. Then check it didn't fail at once.
nohup "$VENV/bin/python" -m journal_app >"$VENV/app.log" 2>&1 &
pid=$!
sleep 3
if ! kill -0 "$pid" 2>/dev/null && ! wait "$pid"; then
    if grep -q "xcb-cursor" "$VENV/app.log"; then
        fail "One system package is missing. On Debian or Ubuntu, run:  sudo apt install libxcb-cursor0   then try again."
    fi
    cat "$VENV/app.log"
    fail "My Journal stopped unexpectedly. The details are above."
fi
