from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from finance_app.ui.icons import icon

DEFAULT_FILE_PATH = str(Path.home() / "finance_data.enc")
LOGO_PATH = Path(__file__).parents[2] / "resources" / "logo_full.png"


class UnlockDialog(QDialog):
    """Prompts for the data file location and master password.

    If the chosen file doesn't exist yet, the password field doubles as
    "set a new master password" and a confirmation field appears.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unlock Finance Data")
        self.setMinimumWidth(420)

        logo_label = QLabel()
        logo_label.setPixmap(
            QPixmap(str(LOGO_PATH)).scaledToWidth(220, Qt.TransformationMode.SmoothTransformation)
        )
        logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.file_path_edit = QLineEdit(DEFAULT_FILE_PATH)
        browse_btn = QPushButton(icon("browse"), "Browse…")
        browse_btn.clicked.connect(self._browse)
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_path_edit)
        file_row.addWidget(browse_btn)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_label = QLabel("Confirm password")

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Data file", file_row)
        form.addRow("Master password", self.password_edit)
        form.addRow(self.confirm_label, self.confirm_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(logo_label)
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addWidget(buttons)

        self.file_path_edit.textChanged.connect(self._update_mode)
        self._update_mode()

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Choose data file", self.file_path_edit.text(), "Encrypted data (*.enc)"
        )
        if path:
            self.file_path_edit.setText(path)

    def _is_new_file(self) -> bool:
        return not Path(self.file_path_edit.text()).expanduser().exists()

    def _update_mode(self) -> None:
        is_new = self._is_new_file()
        self.confirm_label.setVisible(is_new)
        self.confirm_edit.setVisible(is_new)
        self.status_label.setText(
            "No file found at this path — a new encrypted file will be created."
            if is_new
            else "Enter your master password to unlock."
        )

    def _on_accept(self) -> None:
        password = self.password_edit.text()
        if not password:
            QMessageBox.warning(self, "Missing password", "Please enter a master password.")
            return
        if self._is_new_file():
            if len(password) < 8:
                QMessageBox.warning(
                    self, "Weak password", "Use at least 8 characters for a new master password."
                )
                return
            if password != self.confirm_edit.text():
                QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
                return
        self.accept()

    @property
    def file_path(self) -> str:
        return str(Path(self.file_path_edit.text()).expanduser())

    @property
    def password(self) -> str:
        return self.password_edit.text()
