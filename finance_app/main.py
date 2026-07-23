from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from finance_app.data.database import DatabaseManager
from finance_app.security.crypto import WrongPassword
from finance_app.settings import AppSettings
from finance_app.sync.drive_auth import DriveAuthManager
from finance_app.sync.drive_client import DriveClient
from finance_app.sync.drive_sync_service import DriveSyncService
from finance_app.ui.dialogs.drive_picker_dialog import DrivePickerDialog
from finance_app.ui.dialogs.file_source_dialog import FileSourceDialog
from finance_app.ui.dialogs.local_file_choice_dialog import LocalFileChoiceDialog
from finance_app.ui.dialogs.unlock_dialog import UnlockDialog
from finance_app.ui.main_window import MainWindow

RESOURCES_DIR = Path(__file__).parent / "resources"
DRIVE_CACHE_DIR = Path.home() / ".jb_finance_app" / "drive_cache"


class AppController:
    def __init__(self, app: QApplication):
        self.app = app
        self.window: MainWindow | None = None
        self.settings = AppSettings()
        self.auth_manager = DriveAuthManager()
        DRIVE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        self._resolve_file_and_unlock()

    def _resolve_file_and_unlock(self) -> None:
        local_path, drive_file_id = self.settings.get_last_file()
        offer_drive_link = False
        auto_link_new_file = False
        # Set as soon as a Drive-linked file is resolved (existing or
        # remembered), and reused as-is for the whole session — must stay
        # the SAME instance that did the initial pull(), since that's what
        # records the revision push()'s conflict check compares against.
        sync_service: DriveSyncService | None = None

        if local_path is None:
            source_dialog = FileSourceDialog()
            if source_dialog.exec() != QDialog.DialogCode.Accepted:
                self.app.quit()
                return

            if source_dialog.action == FileSourceDialog.ACTION_LOCAL_ONLY:
                local_choice = LocalFileChoiceDialog()
                if local_choice.exec() != QDialog.DialogCode.Accepted:
                    self._resolve_file_and_unlock()
                    return
                local_path = local_choice.chosen_path
                # Still offer to link later — just not automatically, since
                # the user explicitly chose local-only for this file.
                offer_drive_link = True

            elif source_dialog.action == FileSourceDialog.ACTION_GOOGLE:
                try:
                    creds = self.auth_manager.get_credentials()
                    client = DriveClient(creds)
                    folder_id = client.find_or_create_app_folder()
                    files = client.list_enc_files(folder_id)
                except Exception as exc:
                    QMessageBox.critical(None, "Could not connect to Google Drive", str(exc))
                    self._resolve_file_and_unlock()
                    return

                if files:
                    picker = DrivePickerDialog(self.auth_manager, preset_files=files)
                    if picker.exec() != QDialog.DialogCode.Accepted or picker.selected_file_id is None:
                        self._resolve_file_and_unlock()
                        return
                    drive_file_id = picker.selected_file_id
                    local_path = str(DRIVE_CACHE_DIR / f"{drive_file_id}.enc")
                    sync_service = DriveSyncService(self.auth_manager, local_path, drive_file_id)
                    try:
                        sync_service.pull()
                    except Exception as exc:
                        QMessageBox.critical(None, "Could not open Drive file", str(exc))
                        self._resolve_file_and_unlock()
                        return
                else:
                    # Nothing in the JB Financial folder yet — create a new
                    # file locally, then upload it there once unlocked.
                    local_path = str(DRIVE_CACHE_DIR / "new_finance_data.enc")
                    auto_link_new_file = True
        elif drive_file_id:
            # Always pull the latest Drive copy before unlocking a linked
            # file, regardless of the auto-sync toggle — this is what
            # prevents editing stale data and hitting a conflict on save;
            # the toggle only controls whether local edits push back out.
            sync_service = DriveSyncService(self.auth_manager, local_path, drive_file_id)
            try:
                sync_service.pull()
            except Exception as exc:
                QMessageBox.warning(
                    None,
                    "Drive sync",
                    f"Could not refresh from Google Drive, using the last cached copy:\n{exc}",
                )

        dialog = UnlockDialog()
        dialog.file_path_edit.setText(local_path)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            if dialog.use_different_source:
                self.settings.clear_last_file()
                self._resolve_file_and_unlock()
                return
            self.app.quit()
            return

        db = DatabaseManager(dialog.file_path)
        try:
            db.unlock(dialog.password)
        except WrongPassword:
            QMessageBox.critical(None, "Unlock failed", "Incorrect master password.")
            self._resolve_file_and_unlock()
            return
        except Exception as exc:  # pragma: no cover - defensive UI feedback
            QMessageBox.critical(None, "Error", f"Could not open data file:\n{exc}")
            self._resolve_file_and_unlock()
            return

        self.settings.set_last_file(dialog.file_path, drive_file_id)

        if auto_link_new_file and sync_service is None:
            # User explicitly chose "Link with Google Account" up front, so
            # there's no need to ask again — just link it into the shared
            # JB Financial Drive folder.
            sync_service = DriveSyncService(self.auth_manager, dialog.file_path)
            try:
                new_file_id = sync_service.link_new_file()
            except Exception as exc:
                QMessageBox.warning(None, "Could not link to Drive", str(exc))
                sync_service = None
            else:
                self.settings.set_last_file(dialog.file_path, new_file_id)
                self.settings.set_drive_sync_enabled(True)
        elif offer_drive_link and sync_service is None:
            link_now = QMessageBox.question(
                None,
                "Link to Google Drive?",
                "Link this file to Google Drive now, so changes sync automatically?",
            )
            if link_now == QMessageBox.StandardButton.Yes:
                sync_service = DriveSyncService(self.auth_manager, dialog.file_path)
                try:
                    new_file_id = sync_service.link_new_file()
                except Exception as exc:
                    QMessageBox.warning(None, "Could not link to Drive", str(exc))
                    sync_service = None
                else:
                    self.settings.set_last_file(dialog.file_path, new_file_id)
                    self.settings.set_drive_sync_enabled(True)

        self.window = MainWindow(
            db,
            on_locked=self._resolve_file_and_unlock,
            sync_service=sync_service,
            settings=self.settings,
            auth_manager=self.auth_manager,
        )
        self.window.show()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Personal Finance")
    app.setWindowIcon(QIcon(str(RESOURCES_DIR / "logo_icon.png")))
    controller = AppController(app)
    controller.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
