"""Encrypted-file-backed SQLite session management.

The portable file on disk (e.g. in a synced Dropbox folder) is always the
Fernet-encrypted blob written by security/crypto.py. To work with it we
decrypt to a private temp file, point SQLAlchemy at that temp file, and
re-encrypt + delete the temp file on save/lock/exit.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from finance_app.data.models import Base
from finance_app.security import crypto
from finance_app.security.vault_crypto import vault_key_from_root


class DatabaseManager:
    def __init__(self, encrypted_path: str | Path):
        self.encrypted_path = Path(encrypted_path)
        self._temp_dir = Path(tempfile.mkdtemp(prefix="finance_app_"))
        self._temp_db_path = self._temp_dir / "working.sqlite3"
        self._salt: bytes | None = None
        self.finance_key: bytes | None = None
        self.root_key: bytes | None = None
        self.engine = None
        self.SessionLocal: sessionmaker[Session] | None = None

    @property
    def is_new_file(self) -> bool:
        return not self.encrypted_path.exists()

    def unlock(self, password: str) -> None:
        """Decrypt the portable file (or initialize a new one) and open the DB."""
        if self.is_new_file:
            salt = crypto.generate_salt()
            keys = crypto.unlock(password, salt)
            self.root_key = keys.root_key
            self.finance_key = keys.finance_key
            self._temp_db_path.touch()
            self._open_engine()
            self._salt = salt
            self.save()
        else:
            with open(self.encrypted_path, "rb") as f:
                raw = f.read()
            salt, token = raw[: crypto.SALT_SIZE], raw[crypto.SALT_SIZE :]
            keys = crypto.unlock(password, salt)
            plaintext = crypto.decrypt_bytes(token, keys.finance_key)
            self._temp_db_path.write_bytes(plaintext)
            self.root_key = keys.root_key
            self.finance_key = keys.finance_key
            self._salt = salt
            self._open_engine()

        # Idempotent: only creates tables that don't exist yet, so this also
        # brings older data files up to date when new modules add tables.
        Base.metadata.create_all(self.engine)

    def _open_engine(self) -> None:
        self.engine = create_engine(f"sqlite:///{self._temp_db_path}")

        @event.listens_for(self.engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def save(self) -> None:
        """Re-encrypt the current working DB state onto the portable file.

        Disposes pooled connections first so the on-disk temp file reflects
        every committed change; the engine reconnects lazily on next use, so
        existing sessions/engines keep working afterward.
        """
        if self.engine is None or self.finance_key is None:
            raise RuntimeError("Database is not unlocked.")
        self.engine.dispose()
        plaintext = self._temp_db_path.read_bytes()
        token = crypto.encrypt_bytes(plaintext, self.finance_key)
        self.encrypted_path.write_bytes(self._salt + token)

    def lock(self) -> None:
        """Save, drop keys from memory, and remove the temp working directory."""
        if self.engine is not None:
            self.save()
            self.engine.dispose()
        self.finance_key = None
        self.root_key = None
        self.engine = None
        self.SessionLocal = None
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def session(self) -> Session:
        if self.SessionLocal is None:
            raise RuntimeError("Database is not unlocked.")
        return self.SessionLocal()

    @property
    def vault_key(self) -> bytes:
        if self.root_key is None:
            raise RuntimeError("Database is not unlocked.")
        return vault_key_from_root(self.root_key)
