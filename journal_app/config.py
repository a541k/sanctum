"""App preferences (vault location, theme, last backup) kept in a small JSON file.

The file lives in the user's config folder, *outside* the vault, and holds nothing secret.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def default_config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "EncryptedJournal" / "config.json"


class Config:
    DEFAULTS = {"vault_path": str(Path.home() / "JournalVault"), "theme": "light", "last_backup": ""}

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else default_config_path()
        self.data = dict(self.DEFAULTS)
        try:
            self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    @property
    def vault_path(self) -> Path:
        return Path(self.data["vault_path"])

    @vault_path.setter
    def vault_path(self, value) -> None:
        self.data["vault_path"] = str(value)

    @property
    def theme(self) -> str:
        return self.data["theme"]

    @theme.setter
    def theme(self, value: str) -> None:
        self.data["theme"] = value

    @property
    def last_backup(self) -> str:
        return self.data["last_backup"]

    @last_backup.setter
    def last_backup(self, value: str) -> None:
        self.data["last_backup"] = value
