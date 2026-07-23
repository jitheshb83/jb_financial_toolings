"""Small persisted app settings: which file was last opened, and whether
Google Drive sync is enabled for it. Uses Qt's built-in QSettings (no new
dependency) rather than a custom config file."""
from __future__ import annotations

from PySide6.QtCore import QSettings

_ORG = "JithOnline"
_APP = "PersonalFinance"

_LAST_PATH_KEY = "sync/last_local_path"
_LAST_DRIVE_FILE_ID_KEY = "sync/last_drive_file_id"
_SYNC_ENABLED_KEY = "sync/enabled"


class AppSettings:
    def __init__(self) -> None:
        self._settings = QSettings(_ORG, _APP)

    def get_last_file(self) -> tuple[str | None, str | None]:
        """Returns (local_path, drive_file_id). Both None if nothing remembered yet."""
        path = self._settings.value(_LAST_PATH_KEY, None)
        drive_file_id = self._settings.value(_LAST_DRIVE_FILE_ID_KEY, None)
        return path, drive_file_id

    def set_last_file(self, local_path: str, drive_file_id: str | None) -> None:
        self._settings.setValue(_LAST_PATH_KEY, local_path)
        if drive_file_id:
            self._settings.setValue(_LAST_DRIVE_FILE_ID_KEY, drive_file_id)
        else:
            self._settings.remove(_LAST_DRIVE_FILE_ID_KEY)

    def clear_last_file(self) -> None:
        self._settings.remove(_LAST_PATH_KEY)
        self._settings.remove(_LAST_DRIVE_FILE_ID_KEY)

    def is_drive_sync_enabled(self) -> bool:
        value = self._settings.value(_SYNC_ENABLED_KEY, False)
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)

    def set_drive_sync_enabled(self, enabled: bool) -> None:
        self._settings.setValue(_SYNC_ENABLED_KEY, enabled)
