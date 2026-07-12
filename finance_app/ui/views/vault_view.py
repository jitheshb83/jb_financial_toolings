from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from finance_app.security.clipboard import copy_with_autoclear
from finance_app.services.vault_service import VaultService
from finance_app.ui.dialogs.vault_item_dialog import FIELD_SCHEMAS, VaultItemDialog
from finance_app.ui.icons import icon

COLUMNS = ["Title", "Type", "Folder", "Tags"]


class VaultView(QWidget):
    def __init__(self, vault_service: VaultService, on_activity=None, parent=None):
        super().__init__(parent)
        self.vault = vault_service
        self._on_activity = on_activity or (lambda: None)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by title, folder, or tag…")
        self.search_edit.textChanged.connect(self.refresh)

        add_btn = QPushButton(icon("add"), "Add")
        edit_btn = QPushButton(icon("edit"), "Edit")
        delete_btn = QPushButton(icon("delete"), "Delete")
        copy_btn = QPushButton(icon("copy"), "Copy secret")
        add_btn.clicked.connect(self._add_item)
        edit_btn.clicked.connect(self._edit_selected)
        delete_btn.clicked.connect(self._delete_selected)
        copy_btn.clicked.connect(self._copy_selected_secret)

        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(copy_btn)
        btn_row.addStretch()

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._edit_selected)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_edit)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        self._items = []
        self.refresh()

    def refresh(self) -> None:
        query = self.search_edit.text().strip().lower()
        self._items = self.vault.list_items()
        if query:
            self._items = [
                i
                for i in self._items
                if query in (i.title or "").lower()
                or query in (i.folder or "").lower()
                or query in (i.tags or "").lower()
            ]
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self.table.setItem(row, 0, QTableWidgetItem(item.title))
            self.table.setItem(row, 1, QTableWidgetItem(item.type))
            self.table.setItem(row, 2, QTableWidgetItem(item.folder or ""))
            self.table.setItem(row, 3, QTableWidgetItem(item.tags or ""))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.id)

    def _selected_item_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _add_item(self) -> None:
        dialog = VaultItemDialog(self)
        if dialog.exec():
            self.vault.create_item(
                type=dialog.item_type,
                title=dialog.title,
                fields=dialog.fields,
                folder=dialog.folder,
                tags=dialog.tags,
            )
            self._on_activity()
            self.refresh()

    def _edit_selected(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            return
        meta = next(i for i in self._items if i.id == item_id)
        payload = self.vault.get_payload(item_id)
        dialog = VaultItemDialog(
            self,
            item_type=meta.type,
            title=meta.title,
            folder=meta.folder or "",
            tags=meta.tags or "",
            fields=payload,
        )
        if dialog.exec():
            self.vault.update_item(
                item_id,
                title=dialog.title,
                fields=dialog.fields,
                folder=dialog.folder or "",
                tags=dialog.tags or "",
            )
            self._on_activity()
            self.refresh()

    def _delete_selected(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            return
        if (
            QMessageBox.question(self, "Delete item", "Delete this vault item?")
            == QMessageBox.StandardButton.Yes
        ):
            self.vault.delete_item(item_id)
            self._on_activity()
            self.refresh()

    def _copy_selected_secret(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            return
        meta = next(i for i in self._items if i.id == item_id)
        payload = self.vault.get_payload(item_id)
        # Prefer "password" if present, otherwise the first schema field with content.
        secret = payload.get("password")
        if not secret:
            for key, _, _ in FIELD_SCHEMAS[meta.type]:
                if payload.get(key):
                    secret = payload[key]
                    break
        if secret:
            copy_with_autoclear(secret)
            self._on_activity()
