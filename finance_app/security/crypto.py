"""Master-password key derivation and whole-file encryption.

Key hierarchy:
    master password --Argon2id--> root_key (32 bytes)
    root_key --HKDF(info=b"finance")--> finance_key  (encrypts the SQLite file)
    root_key --HKDF(info=b"vault")-->   vault_key    (security/vault_crypto.py)
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SALT_SIZE = 16
ROOT_KEY_SIZE = 32

# Argon2id cost parameters. time_cost/memory_cost are deliberately expensive
# (~0.5-1s on modern hardware) since this only runs once per unlock.
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST_KIB = 256 * 1024  # 256 MiB
ARGON2_PARALLELISM = 4


class WrongPassword(Exception):
    """Raised when a file fails to decrypt with the given password."""


def generate_salt() -> bytes:
    return os.urandom(SALT_SIZE)


def derive_root_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte root key from the master password via Argon2id."""
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST_KIB,
        parallelism=ARGON2_PARALLELISM,
        hash_len=ROOT_KEY_SIZE,
        type=Type.ID,
    )


def derive_subkey(root_key: bytes, info: bytes, length: int = 32) -> bytes:
    """Split the root key into an independent subkey via HKDF-SHA256."""
    hkdf = HKDF(algorithm=hashes.SHA256(), length=length, salt=None, info=info)
    return hkdf.derive(root_key)


def finance_key_from_root(root_key: bytes) -> bytes:
    return derive_subkey(root_key, b"finance_key")


def _fernet_key(raw_key: bytes) -> bytes:
    """Fernet requires a url-safe base64-encoded 32-byte key."""
    return base64.urlsafe_b64encode(raw_key)


@dataclass
class UnlockedKeys:
    root_key: bytes
    finance_key: bytes


def unlock(password: str, salt: bytes) -> UnlockedKeys:
    root_key = derive_root_key(password, salt)
    return UnlockedKeys(root_key=root_key, finance_key=finance_key_from_root(root_key))


def encrypt_bytes(plaintext: bytes, finance_key: bytes) -> bytes:
    return Fernet(_fernet_key(finance_key)).encrypt(plaintext)


def decrypt_bytes(token: bytes, finance_key: bytes) -> bytes:
    try:
        return Fernet(_fernet_key(finance_key)).decrypt(token)
    except InvalidToken as exc:
        raise WrongPassword("Incorrect master password or corrupted file.") from exc


def encrypt_file(plaintext_path: str, encrypted_path: str, password: str) -> bytes:
    """Encrypt plaintext_path into encrypted_path as [salt][fernet token].

    Returns the salt used, so callers can persist/reuse it.
    """
    salt = generate_salt()
    keys = unlock(password, salt)
    with open(plaintext_path, "rb") as f:
        plaintext = f.read()
    token = encrypt_bytes(plaintext, keys.finance_key)
    with open(encrypted_path, "wb") as f:
        f.write(salt + token)
    return salt


def decrypt_file(encrypted_path: str, plaintext_path: str, password: str) -> UnlockedKeys:
    """Decrypt encrypted_path (as written by encrypt_file) into plaintext_path."""
    with open(encrypted_path, "rb") as f:
        raw = f.read()
    salt, token = raw[:SALT_SIZE], raw[SALT_SIZE:]
    keys = unlock(password, salt)
    plaintext = decrypt_bytes(token, keys.finance_key)
    with open(plaintext_path, "wb") as f:
        f.write(plaintext)
    return keys
