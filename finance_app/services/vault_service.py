from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from finance_app.data.models import VaultItem
from finance_app.security.vault_crypto import decrypt_item, encrypt_item

VALID_TYPES = {"login", "secure_note", "card", "identity"}


class VaultItemMeta:
    """Lightweight view of a vault item without its decrypted payload."""

    def __init__(self, item: VaultItem):
        self.id = item.id
        self.type = item.type
        self.title = item.title
        self.folder = item.folder
        self.tags = item.tags
        self.updated_at = item.updated_at


class VaultService:
    """CRUD for vault items. Enforces AES-256-GCM encryption on every
    payload write/read using the vault_key (independent from finance_key).
    """

    def __init__(self, session: Session, vault_key: bytes):
        self.session = session
        self.vault_key = vault_key

    def list_items(self) -> list[VaultItemMeta]:
        items = self.session.query(VaultItem).order_by(VaultItem.title).all()
        return [VaultItemMeta(i) for i in items]

    def create_item(
        self,
        type: str,
        title: str,
        fields: dict,
        folder: str | None = None,
        tags: str | None = None,
    ) -> int:
        if type not in VALID_TYPES:
            raise ValueError(f"Unknown vault item type: {type}")
        nonce, ciphertext = encrypt_item(json.dumps(fields).encode("utf-8"), self.vault_key)
        now = datetime.now(timezone.utc)
        item = VaultItem(
            type=type,
            title=title,
            folder=folder,
            tags=tags,
            payload_nonce=nonce,
            payload_ciphertext=ciphertext,
            created_at=now,
            updated_at=now,
        )
        self.session.add(item)
        self.session.commit()
        return item.id

    def get_payload(self, item_id: int) -> dict:
        item = self.session.get(VaultItem, item_id)
        if item is None:
            raise KeyError(f"No vault item with id {item_id}")
        plaintext = decrypt_item(item.payload_nonce, item.payload_ciphertext, self.vault_key)
        return json.loads(plaintext.decode("utf-8"))

    def update_item(
        self,
        item_id: int,
        title: str | None = None,
        fields: dict | None = None,
        folder: str | None = None,
        tags: str | None = None,
    ) -> None:
        item = self.session.get(VaultItem, item_id)
        if item is None:
            raise KeyError(f"No vault item with id {item_id}")
        if title is not None:
            item.title = title
        if folder is not None:
            item.folder = folder
        if tags is not None:
            item.tags = tags
        if fields is not None:
            nonce, ciphertext = encrypt_item(json.dumps(fields).encode("utf-8"), self.vault_key)
            item.payload_nonce = nonce
            item.payload_ciphertext = ciphertext
        item.updated_at = datetime.now(timezone.utc)
        self.session.commit()

    def delete_item(self, item_id: int) -> None:
        item = self.session.get(VaultItem, item_id)
        if item is None:
            raise KeyError(f"No vault item with id {item_id}")
        self.session.delete(item)
        self.session.commit()
