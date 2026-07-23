"""Thin wrapper around the Drive v3 API, scoped to `drive.file` — the app
only ever sees files it created or the user explicitly opened through the
picker, never the user's whole Drive.
"""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

ENC_MIME_TYPE = "application/octet-stream"
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
FOLDER_NAME = "JB Financial"


class DriveFileMeta(TypedDict):
    id: str
    name: str
    modifiedTime: str
    headRevisionId: str


class DriveClient:
    def __init__(self, credentials: Credentials):
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    def find_or_create_app_folder(self) -> str:
        """Every file this app creates on Drive lives in one dedicated,
        visible folder (FOLDER_NAME) in the user's My Drive, rather than
        scattered loose files — makes it a single predictable place to find
        and browse them outside the app too."""
        result = (
            self._service.files()
            .list(
                q=f"name = '{FOLDER_NAME}' and mimeType = '{FOLDER_MIME_TYPE}' and trashed = false",
                fields="files(id, name)",
                spaces="drive",
            )
            .execute()
        )
        existing = result.get("files", [])
        if existing:
            return existing[0]["id"]
        created = (
            self._service.files()
            .create(body={"name": FOLDER_NAME, "mimeType": FOLDER_MIME_TYPE}, fields="id")
            .execute()
        )
        return created["id"]

    def list_enc_files(self, folder_id: str | None = None) -> list[DriveFileMeta]:
        query = "name contains '.enc' and trashed = false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        result = (
            self._service.files()
            .list(
                q=query,
                fields="files(id, name, modifiedTime, headRevisionId)",
                spaces="drive",
            )
            .execute()
        )
        return result.get("files", [])

    def get_metadata(self, file_id: str) -> DriveFileMeta:
        return (
            self._service.files()
            .get(fileId=file_id, fields="id, name, modifiedTime, headRevisionId")
            .execute()
        )

    def create_file(
        self, local_path: str | Path, name: str, parent_folder_id: str | None = None
    ) -> DriveFileMeta:
        """Uploads local_path as a brand-new Drive file, inside
        parent_folder_id if given. Requests the same fields as
        get_metadata() in this one call, so callers don't need a separate
        round-trip just to learn the new file's revision id."""
        media = MediaFileUpload(str(local_path), mimetype=ENC_MIME_TYPE, resumable=False)
        body = {"name": name}
        if parent_folder_id:
            body["parents"] = [parent_folder_id]
        return (
            self._service.files()
            .create(body=body, media_body=media, fields="id, name, modifiedTime, headRevisionId")
            .execute()
        )

    def upload_file(self, file_id: str, local_path: str | Path) -> str:
        """Replaces an existing Drive file's content in place (never creates
        a duplicate). Returns the new headRevisionId directly from the
        upload response, avoiding a separate get_metadata() call."""
        media = MediaFileUpload(str(local_path), mimetype=ENC_MIME_TYPE, resumable=False)
        result = (
            self._service.files()
            .update(fileId=file_id, media_body=media, fields="headRevisionId")
            .execute()
        )
        return result["headRevisionId"]

    def download_file(self, file_id: str, dest_path: str | Path) -> None:
        request = self._service.files().get_media(fileId=file_id)
        dest = Path(dest_path)
        with open(dest, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _status, done = downloader.next_chunk()
