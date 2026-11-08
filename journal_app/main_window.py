"""Main window: a slim top bar plus a stack of pages (home, browse, entry, settings)."""
from __future__ import annotations

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from .config import Config
from .dialogs import authenticate
from .pages import BrowsePage, EntryPage, HomePage, Page, SettingsPage
from .vault import Vault
from .widgets import make_button, make_label


class MainWindow(QMainWindow):
    def __init__(self, vault: Vault, config: Config):
        super().__init__()
        self.vault = vault
        self.config = config
        self.history: list[Page] = []
        self.setWindowTitle("My Journal")
        self.resize(1120, 780)
        self.setMinimumSize(900, 620)

        # top bar
        self.back_btn = make_button("Back", "ghost", "arrow_left")
        self.back_btn.clicked.connect(self.go_back)
        self.home_btn = make_button("Home", "ghost", "home")
        self.home_btn.clicked.connect(self.go_home)
        self.lock_btn = make_button("Lock", "ghost", "lock")
        self.lock_btn.clicked.connect(self.lock)
        bar = QFrame()
        bar.setObjectName("topbar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 8, 16, 8)
        bl.addWidget(self.back_btn)
        bl.addWidget(make_label("My Journal", "brand"))
        bl.addStretch()
        bl.addWidget(self.home_btn)
        bl.addWidget(self.lock_btn)

        # pages
        self.stack = QStackedWidget()
        self.home = HomePage(self)
        self.browse = BrowsePage(self)
        self.entry = EntryPage(self)
        self.settings = SettingsPage(self)
        for p in (self.home, self.browse, self.entry, self.settings):
            self.stack.addWidget(p)

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(bar)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_entry)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.lock)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._save_shortcut)
        QShortcut(QKeySequence("Alt+Left"), self, activated=self.go_back)

        self.navigate(self.home, push=False)
        self._warn_load_errors()

    # ---- navigation ------------------------------------------------------
    @property
    def current(self) -> Page:
        return self.stack.currentWidget()

    def navigate(self, page: Page, push: bool = True) -> bool:
        cur = self.current
        if page is cur:
            self._update_chrome()
            page.on_show()
            return True
        if cur is not None and not cur.can_leave():
            return False
        if push and cur is not None:
            self.history.append(cur)
        self.stack.setCurrentWidget(page)
        self._update_chrome()
        page.on_show()
        return True

    def _update_chrome(self) -> None:
        at_home = self.current is self.home
        self.back_btn.setVisible(not at_home)
        self.home_btn.setVisible(not at_home)

    def go_home(self) -> None:
        if self.navigate(self.home, push=False):
            self.history.clear()

    def go_back(self) -> None:
        if not self.history:
            return self.go_home()
        target = self.history[-1]
        if self.navigate(target, push=False):
            self.history.pop()

    def show_browse(self, tab: int = 0) -> None:
        self.browse.show_tab(tab)
        self.navigate(self.browse)

    def show_settings(self) -> None:
        self.navigate(self.settings)

    def new_entry(self) -> None:
        if self.navigate(self.entry):
            self.entry.open_new()

    def open_entry(self, entry_id: str) -> None:
        if self.navigate(self.entry):
            self.entry.open_existing(entry_id)

    def _save_shortcut(self) -> None:
        if self.current is self.entry:
            self.entry.save()

    # ---- session ---------------------------------------------------------
    def lock(self) -> None:
        if not self.current.can_leave():
            return
        self.entry.editor.clear()
        self.history.clear()
        self.navigate(self.home, push=False)  # before vault.lock(): Home reads the vault when shown
        self.vault.lock()
        self.hide()
        vault = authenticate(self.config.vault_path)
        if vault is None:
            QApplication.quit()
            return
        self.vault = vault
        self.navigate(self.home, push=False)
        self.show()
        self._warn_load_errors()

    def _warn_load_errors(self) -> None:
        if self.vault.load_errors:
            QMessageBox.warning(
                self, "Some entries couldn't be read",
                "These files are damaged or were changed outside the app, so they were skipped:\n\n"
                + "\n".join(self.vault.load_errors[:10]))

    def closeEvent(self, event) -> None:
        if not self.current.can_leave():
            event.ignore()
            return
        event.accept()
        QApplication.quit()
