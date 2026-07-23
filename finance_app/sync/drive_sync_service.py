"""Mirrors a local .enc file to/from a single linked Google Drive file.

The local file (managed by DatabaseManager) is always the primary working
copy — this service only pulls the remote copy down before it's read, and
pushes the local copy up after it's saved. It never touches DatabaseManager
or the SQLite/crypto logic directly.
"""
from __future__ import annotations

from pathlib import Path

from finance_app.sync.drive_auth import DriveAuthManager
from finance_app.sync.drive_client import DriveClient


class DriveConflictError(Exception):
    """Raised when the linked Drive file changed remotely since it was last
    pulled, so an upload would silently clobber someone else's edit."""


class DriveSyncService:
    def __init__(self, auth_manager: DriveAuthManager, local_path: str | Path, file_id: str | None = None):
        self._auth_manager = auth_manager
        self._local_path = Path(local_path)
        self.file_id = file_id
        self._last_known_revision: str | None = None
        self._client_cache: DriveClient | None = None

    def _client(self) -> DriveClient:
        """Cached per service instance — building a Drive API client
        (googleapiclient.discovery.build) isn't free, and the underlying
        credentials object refreshes itself in place, so there's no need to
        rebuild this on every pull()/push()/check_for_remote_changes()."""
        if self._client_cache is None:
            self._client_cache = DriveClient(self._auth_manager.get_credentials())
        return self._client_cache

    def link_new_file(self, drive_name: str | None = None) -> str:
        """Uploads the local file as a brand-new Drive file, inside this
        app's dedicated Drive folder (DriveClient.FOLDER_NAME), and links it.
        Used right after a new local file is created."""
        name = drive_name or self._local_path.name
        client = self._client()
        folder_id = client.find_or_create_app_folder()
        meta = client.create_file(self._local_path, name, parent_folder_id=folder_id)
        self.file_id = meta["id"]
        self._last_known_revision = meta["headRevisionId"]
        return self.file_id

    def pull(self) -> None:
        """Downloads the linked Drive file's current bytes over the local
        working path, and records its revision for conflict detection."""
        if self.file_id is None:
            raise RuntimeError("No Drive file linked yet.")
        client = self._client()
        client.download_file(self.file_id, self._local_path)
        meta = client.get_metadata(self.file_id)
        self._last_known_revision = meta["headRevisionId"]

    def check_for_remote_changes(self) -> bool:
        if self.file_id is None:
            raise RuntimeError("No Drive file linked yet.")
        meta = self._client().get_metadata(self.file_id)
        return meta["headRevisionId"] != self._last_known_revision

    def push(self) -> None:
        """Uploads the local working file over the linked Drive file.
        Raises DriveConflictError instead of silently overwriting if the
        remote file changed since the last pull()/push()."""
        if self.file_id is None:
            raise RuntimeError("No Drive file linked yet.")
        if self.check_for_remote_changes():
            raise DriveConflictError(
                "The linked Google Drive file changed remotely since it was last synced. "
                "Re-open the file to get the latest version before continuing."
            )
        self._last_known_revision = self._client().upload_file(self.file_id, self._local_path)
