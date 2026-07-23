"""First-run (or "use a different file") screen: link with a Google
account, or use local storage only. Shown only when there's no remembered
file (see finance_app/settings.py)."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class FileSourceDialog(QDialog):
    ACTION_GOOGLE = "google"
    ACTION_LOCAL_ONLY = "local_only"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Finance Data")
        self.setMinimumWidth(360)
        self.action: str | None = None

        google_btn = QPushButton("Link with Google Account")
        local_btn = QPushButton("Use Local Only")
        google_btn.clicked.connect(self._on_google)
        local_btn.clicked.connect(self._on_local_only)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("How would you like to store your finance data?"))
        layout.addWidget(google_btn)
        layout.addWidget(local_btn)
        layout.addWidget(
            QLabel(
                "Linking with Google stores your encrypted file in a dedicated "
                "\"JB Financial\" folder in your Google Drive and keeps it synced."
            )
        )

    def _on_google(self) -> None:
        self.action = self.ACTION_GOOGLE
        self.accept()

    def _on_local_only(self) -> None:
        self.action = self.ACTION_LOCAL_ONLY
        self.accept()
