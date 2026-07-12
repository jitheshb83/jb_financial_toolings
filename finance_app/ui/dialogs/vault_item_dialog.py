from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

# type -> ordered list of (field_key, label, is_multiline)
FIELD_SCHEMAS: dict[str, list[tuple[str, str, bool]]] = {
    "login": [
        ("username", "Username", False),
        ("password", "Password", False),
        ("url", "URL", False),
        ("notes", "Notes", True),
    ],
    "secure_note": [
        ("notes", "Note", True),
    ],
    "card": [
        ("cardholder", "Cardholder name", False),
        ("number", "Card number", False),
        ("expiry", "Expiry (MM/YY)", False),
        ("cvv", "CVV", False),
        ("notes", "Notes", True),
    ],
    "identity": [
        ("full_name", "Full name", False),
        ("id_number", "ID number", False),
        ("address", "Address", True),
        ("notes", "Notes", True),
    ],
}


class VaultItemDialog(QDialog):
    """Add/edit dialog for a vault item. When `fields` is provided the
    dialog is pre-populated for editing; otherwise it starts blank.
    """

    def __init__(
        self,
        parent=None,
        item_type: str = "login",
        title: str = "",
        folder: str = "",
        tags: str = "",
        fields: dict | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Vault Item")
        self.setMinimumWidth(420)
        self._field_edits: dict[str, QLineEdit | QPlainTextEdit] = {}

        self.type_combo = QComboBox()
        self.type_combo.addItems(list(FIELD_SCHEMAS.keys()))
        self.type_combo.setCurrentText(item_type)
        self.type_combo.currentTextChanged.connect(self._rebuild_fields)

        self.title_edit = QLineEdit(title)
        self.folder_edit = QLineEdit(folder)
        self.tags_edit = QLineEdit(tags)

        self.top_form = QFormLayout()
        self.top_form.addRow("Type", self.type_combo)
        self.top_form.addRow("Title", self.title_edit)
        self.top_form.addRow("Folder", self.folder_edit)
        self.top_form.addRow("Tags", self.tags_edit)

        self.fields_form = QFormLayout()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(self.top_form)
        layout.addLayout(self.fields_form)
        layout.addWidget(buttons)

        self._rebuild_fields(item_type, initial_fields=fields or {})

    def _rebuild_fields(self, item_type: str, initial_fields: dict | None = None) -> None:
        while self.fields_form.rowCount():
            self.fields_form.removeRow(0)
        self._field_edits.clear()
        initial_fields = initial_fields or {}
        for key, label, multiline in FIELD_SCHEMAS[item_type]:
            if multiline:
                edit = QPlainTextEdit(initial_fields.get(key, ""))
                edit.setFixedHeight(70)
            else:
                edit = QLineEdit(initial_fields.get(key, ""))
                if key == "password":
                    edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._field_edits[key] = edit
            self.fields_form.addRow(label, edit)

    @property
    def item_type(self) -> str:
        return self.type_combo.currentText()

    @property
    def title(self) -> str:
        return self.title_edit.text()

    @property
    def folder(self) -> str:
        return self.folder_edit.text() or None

    @property
    def tags(self) -> str:
        return self.tags_edit.text() or None

    @property
    def fields(self) -> dict:
        result = {}
        for key, edit in self._field_edits.items():
            if isinstance(edit, QPlainTextEdit):
                result[key] = edit.toPlainText()
            else:
                result[key] = edit.text()
        return result
