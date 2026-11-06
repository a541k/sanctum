"""Sign-in and password dialogs."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QVBoxLayout,
)

from .vault import InvalidCredentials, Vault
from .widgets import make_button, make_label

MIN_PASSWORD_LEN = 8
Password = QLineEdit.EchoMode.Password


def _password_field() -> QLineEdit:
    f = QLineEdit()
    f.setEchoMode(Password)
    return f


class NewPasswordDialog(QDialog):
    """Choose a password. Pass `verify` to also ask for the current password first."""

    def __init__(self, title: str, intro: str, verify: Callable[[str], bool] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.password = ""
        self._verify = verify
        self.current = _password_field()
        self.pw1, self.pw2 = _password_field(), _password_field()
        self.error = make_label("", "error", wrap=True)
        ok = make_button("Continue", "primary")
        ok.setDefault(True)
        ok.clicked.connect(self._submit)
        cancel = make_button("Cancel")
        cancel.clicked.connect(self.reject)

        form = QFormLayout()
        form.setSpacing(10)
        if verify:
            form.addRow("Current password", self.current)
        form.addRow("New password" if verify else "Password", self.pw1)
        form.addRow("Confirm", self.pw2)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(ok)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(make_label(title, "h1"))
        lay.addWidget(make_label(intro, "muted", wrap=True))
        lay.addLayout(form)
        lay.addWidget(self.error)
        lay.addLayout(buttons)

    def _submit(self):
        if self._verify and not self._verify(self.current.text()):
            self.error.setText("That isn't your current password. Check it and try again.")
        elif len(self.pw1.text()) < MIN_PASSWORD_LEN:
            self.error.setText(f"Use at least {MIN_PASSWORD_LEN} characters.")
        elif self.pw1.text() != self.pw2.text():
            self.error.setText("The two passwords don't match.")
        else:
            self.password = self.pw1.text()
            self.accept()


class RecoveryKeyDialog(QDialog):
    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save your recovery key")
        self.setMinimumWidth(500)
        box = QPlainTextEdit(key)
        box.setReadOnly(True)
        box.setFixedHeight(84)
        copy = make_button("Copy to clipboard")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(key))
        self.saved = QCheckBox("I have saved my recovery key")
        self.done_btn = make_button("Done", "primary")
        self.done_btn.setEnabled(False)
        self.done_btn.clicked.connect(self.accept)
        self.saved.toggled.connect(self.done_btn.setEnabled)

        row = QHBoxLayout()
        row.addWidget(copy)
        row.addStretch()
        row.addWidget(self.done_btn)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(14)
        lay.addWidget(make_label("Save your recovery key", "h1"))
        lay.addWidget(make_label(
            "If you forget your password, this key is the only way to open your journal again. "
            "Write it down or keep it somewhere safe. It won't be shown again.", "muted", wrap=True))
        lay.addWidget(box)
        lay.addWidget(self.saved)
        lay.addLayout(row)

    def reject(self):  # Esc must not skip this step
        pass


class UnlockDialog(QDialog):
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = root
        self.vault: Vault | None = None
        self.used_recovery = False
        self._recovery_mode = False
        self.setWindowTitle("Unlock journal")
        self.setMinimumWidth(400)

        self.prompt = make_label("Password", "muted")
        self.field = _password_field()
        self.field.returnPressed.connect(self._attempt)
        self.error = make_label("", "error", wrap=True)
        self.toggle = make_button("Forgot your password? Use your recovery key", "ghost")
        self.toggle.clicked.connect(self._toggle_mode)
        unlock = make_button("Unlock", "primary")
        unlock.setDefault(True)
        unlock.clicked.connect(self._attempt)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(10)
        lay.addWidget(make_label("Your journal", "h1"))
        lay.addWidget(make_label("Enter your password to continue.", "muted"))
        lay.addSpacing(6)
        lay.addWidget(self.prompt)
        lay.addWidget(self.field)
        lay.addWidget(self.error)
        lay.addWidget(unlock)
        lay.addWidget(self.toggle)

    def _toggle_mode(self):
        self._recovery_mode = not self._recovery_mode
        self.field.clear()
        self.error.clear()
        if self._recovery_mode:
            self.prompt.setText("Recovery key")
            self.field.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle.setText("Use your password instead")
        else:
            self.prompt.setText("Password")
            self.field.setEchoMode(Password)
            self.toggle.setText("Forgot your password? Use your recovery key")

    def _attempt(self):
        try:
            if self._recovery_mode:
                self.vault = Vault.open(self.root, recovery_key=self.field.text())
                self.used_recovery = True
            else:
                self.vault = Vault.open(self.root, password=self.field.text())
        except InvalidCredentials:
            self.error.setText("That recovery key isn't right. Check it and try again."
                               if self._recovery_mode else "That password isn't right. Try again.")
            self.field.selectAll()
            return
        self.accept()


def authenticate(root) -> Vault | None:
    """Create-or-unlock flow. Returns an unlocked Vault, or None if the person cancels."""
    if not Vault.exists(root):
        dlg = NewPasswordDialog(
            "Create your journal",
            f"Choose a password for your new journal. Your entries will be stored, encrypted, in:\n{root}\n\n"
            "There is no way to reset this password. In the next step you'll get a recovery key.")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        vault, recovery = Vault.create(root, dlg.password)
        RecoveryKeyDialog(recovery).exec()
        return vault

    dlg = UnlockDialog(root)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    if dlg.used_recovery:
        pw = NewPasswordDialog("Set a new password",
                               "Your recovery key worked. Choose a new password for your journal.")
        if pw.exec() == QDialog.DialogCode.Accepted:
            dlg.vault.change_password(pw.password)
    return dlg.vault
