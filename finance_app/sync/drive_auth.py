"""Google OAuth sign-in for Drive access.

The resulting refresh token is stored in the OS keychain via `keyring`,
kept separate from the vault's own master password: the master password
gates the finance data itself (zero-knowledge to the OS), while this token
is a device-local transport credential scoped narrowly to
`drive.file` (files this app itself creates/opens) — a different trust
boundary, so conflating the two would force re-auth with Google on every
password change without adding real protection.
"""
from __future__ import annotations

import json
from pathlib import Path

import keyring
import keyring.errors
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CREDENTIALS_PATH = Path(__file__).resolve().parents[1] / "credentials.json"
KEYRING_SERVICE = "jb_finance_app"
KEYRING_USERNAME = "drive_oauth_token"


class DriveAuthError(Exception):
    """Raised when Drive sign-in or credential refresh fails."""


class DriveAuthManager:
    def __init__(self) -> None:
        self._credentials: Credentials | None = None

    def is_signed_in(self) -> bool:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME) is not None

    def sign_out(self) -> None:
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
        except keyring.errors.PasswordDeleteError:
            pass
        self._credentials = None

    def get_credentials(self) -> Credentials:
        """Returns valid credentials, prompting an interactive browser
        sign-in only if no usable stored token exists."""
        if self._credentials and self._credentials.valid:
            return self._credentials

        stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if stored:
            creds = Credentials.from_authorized_user_info(json.loads(stored), SCOPES)
            if creds.valid:
                self._credentials = creds
                return creds
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as exc:
                    raise DriveAuthError(f"Could not refresh Google Drive session: {exc}") from exc
                self._store(creds)
                self._credentials = creds
                return creds

        creds = self._interactive_sign_in()
        self._store(creds)
        self._credentials = creds
        return creds

    def _interactive_sign_in(self) -> Credentials:
        if not CREDENTIALS_PATH.exists():
            raise DriveAuthError(
                f"Missing OAuth client file at {CREDENTIALS_PATH}. Download it from "
                "Google Cloud Console (OAuth Client ID, 'Desktop app' type) and place "
                "it there before using Google Drive sync."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        return flow.run_local_server(port=0)

    def _store(self, creds: Credentials) -> None:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, creds.to_json())
