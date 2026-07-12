"""Per-item vault encryption: AES-256-GCM under a key independent from the
file-level finance_key (see security/crypto.py for the HKDF split)."""
from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from finance_app.security.crypto import derive_subkey

NONCE_SIZE = 12  # 96-bit nonce, standard for GCM


class VaultTamperedOrWrongKey(Exception):
    """Raised when a vault item fails GCM authentication on decrypt."""


def vault_key_from_root(root_key: bytes) -> bytes:
    return derive_subkey(root_key, b"vault_key")


def encrypt_item(plaintext: bytes, vault_key: bytes) -> tuple[bytes, bytes]:
    """Encrypt one vault item's payload. Returns (nonce, ciphertext_with_tag)."""
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = AESGCM(vault_key).encrypt(nonce, plaintext, associated_data=None)
    return nonce, ciphertext


def decrypt_item(nonce: bytes, ciphertext: bytes, vault_key: bytes) -> bytes:
    try:
        return AESGCM(vault_key).decrypt(nonce, ciphertext, associated_data=None)
    except InvalidTag as exc:
        raise VaultTamperedOrWrongKey(
            "Vault item failed authentication (wrong password or corrupted data)."
        ) from exc
