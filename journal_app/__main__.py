import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .config import Config
from .dialogs import authenticate
from .main_window import MainWindow
from .theme import THEME


def main() -> int:
    parser = argparse.ArgumentParser(description="Personal encrypted journal")
    parser.add_argument("--vault", type=Path,
                        help="use (and remember) this folder for the journal instead of the saved location")
    args = parser.parse_args()

    config = Config()
    if args.vault:
        config.vault_path = args.vault.resolve()
        config.save()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # we quit explicitly, so Lock can hide the window
    app.setApplicationName("Journal")
    THEME.init_fonts()
    THEME.apply(config.theme)

    vault = authenticate(config.vault_path)
    if vault is None:
        return 0
    window = MainWindow(vault, config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
