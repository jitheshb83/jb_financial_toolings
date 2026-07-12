from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)


class OtherInvestmentDialog(QDialog):
    def __init__(
        self,
        parent=None,
        name: str = "",
        type: str = "",
        currency: str = "USD",
        value: float = 0.0,
        note: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("Other Investment")
        self.setMinimumWidth(340)

        self.name_edit = QLineEdit(name)
        self.type_edit = QLineEdit(type)
        self.type_edit.setPlaceholderText("gold, real estate, crypto, ...")
        self.currency_edit = QLineEdit(currency)

        self.value_spin = QDoubleSpinBox()
        self.value_spin.setRange(0, 1_000_000_000)
        self.value_spin.setDecimals(2)
        self.value_spin.setValue(value)

        self.note_edit = QLineEdit(note)

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Type", self.type_edit)
        form.addRow("Currency", self.currency_edit)
        form.addRow("Value", self.value_spin)
        form.addRow("Note", self.note_edit)

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
        return self.type_edit.text().strip()

    @property
    def currency(self) -> str:
        return self.currency_edit.text().strip().upper()

    @property
    def value(self) -> float:
        return self.value_spin.value()

    @property
    def note(self) -> str:
        return self.note_edit.text().strip()
