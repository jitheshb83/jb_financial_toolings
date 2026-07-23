"""Lists existing .enc files in this app's dedicated Google Drive folder
(DriveClient.FOLDER_NAME) so the user can pick one to open. If the caller
already resolved the folder and fetched the list (see main.py's Google-
linked first-run flow), pass it in via `preset_files` to skip doing that
work twice; otherwise this dialog signs in and fetches it itself."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from finance_app.sync.drive_auth import DriveAuthError, DriveAuthManager
from finance_app.sync.drive_client import DriveClient, DriveFileMeta


class DrivePickerDialog(QDialog):
    def __init__(
        self,
        auth_manager: DriveAuthManager,
        parent=None,
        preset_files: list[DriveFileMeta] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Open from Google Drive")
        self.setMinimumWidth(420)
        self._auth_manager = auth_manager
        self.selected_file_id: str | None = None
        self.selected_file_name: str | None = None

        self.status_label = QLabel("Signing in to Google…")
        self.status_label.setWordWrap(True)
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_accept)

        open_btn = QPushButton("Open selected")
        open_btn.clicked.connect(self._on_accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(open_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.list_widget)
        layout.addLayout(btn_row)

        if preset_files is not None:
            self._populate(preset_files)
        else:
            self._sign_in_and_list()

    def _sign_in_and_list(self) -> None:
        try:
            creds = self._auth_manager.get_credentials()
            client = DriveClient(creds)
            folder_id = client.find_or_create_app_folder()
            files = client.list_enc_files(folder_id)
        except DriveAuthError as exc:
            self.status_label.setText(str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive UI feedback
            self.status_label.setText(f"Could not reach Google Drive: {exc}")
            return
        self._populate(files)

    def _populate(self, files: list[DriveFileMeta]) -> None:
        if not files:
            self.status_label.setText(
                "No .enc files found in this Drive folder yet. "
                "Create a new local file instead, then link it to Drive."
            )
            return

        self.status_label.setText("Choose a file to open:")
        for f in files:
            item = QListWidgetItem(f["name"])
            item.setData(Qt.ItemDataRole.UserRole, f["id"])
            self.list_widget.addItem(item)

    def _on_accept(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            QMessageBox.warning(self, "No selection", "Select a file to open.")
            return
        self.selected_file_id = item.data(Qt.ItemDataRole.UserRole)
        self.selected_file_name = item.text()
        self.accept()
