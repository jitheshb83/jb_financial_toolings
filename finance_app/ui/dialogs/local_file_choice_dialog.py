"""Shown after the user picks "Use Local Only": create a new local file, or
open an existing one already on disk."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QFileDialog, QLabel, QPushButton, QVBoxLayout

DEFAULT_NEW_PATH = str(Path.home() / "finance_data.enc")


class LocalFileChoiceDialog(QDialog):
    ACTION_CREATE_NEW = "create_new"
    ACTION_OPEN_LOCAL = "open_local"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Local Finance Data")
        self.setMinimumWidth(360)
        self.action: str | None = None
        self.chosen_path: str | None = None

        create_btn = QPushButton("Create a new file")
        open_btn = QPushButton("Open an existing local file…")
        create_btn.clicked.connect(self._on_create_new)
        open_btn.clicked.connect(self._on_open_local)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Create a new file, or open one you already have?"))
        layout.addWidget(create_btn)
        layout.addWidget(open_btn)

    def _on_create_new(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Create new data file", DEFAULT_NEW_PATH, "Encrypted data (*.enc)"
        )
        if not path:
            return
        self.action = self.ACTION_CREATE_NEW
        self.chosen_path = path
        self.accept()

    def _on_open_local(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open data file", str(Path.home()), "Encrypted data (*.enc)"
        )
        if not path:
            return
        self.action = self.ACTION_OPEN_LOCAL
        self.chosen_path = path
        self.accept()
