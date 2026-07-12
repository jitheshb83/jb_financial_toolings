from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout

ACCOUNT_TYPES = ["bank", "cash", "broker"]


class AccountDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Account")

        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(ACCOUNT_TYPES)
        self.currency_edit = QLineEdit("USD")

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Type", self.type_combo)
        form.addRow("Currency", self.currency_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @property
    def name(self) -> str:
        return self.name_edit.text().strip()

    @property
    def type(self) -> str:
        return self.type_combo.currentText()

    @property
    def currency(self) -> str:
        return self.currency_edit.text().strip().upper()
