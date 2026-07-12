from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from finance_app.services.borrowing_service import DIRECTIONS, STATUSES


class BorrowingDialog(QDialog):
    def __init__(
        self,
        parent=None,
        counterparty: str = "",
        direction: str = "lent",
        principal: float = 0.0,
        currency: str = "USD",
        due_date: dt.date | None = None,
        status: str = "pending",
    ):
        super().__init__(parent)
        self.setWindowTitle("Borrowing")
        self.setMinimumWidth(340)

        self.counterparty_edit = QLineEdit(counterparty)

        self.direction_combo = QComboBox()
        self.direction_combo.addItems(DIRECTIONS)
        self.direction_combo.setCurrentText(direction)

        self.principal_spin = QDoubleSpinBox()
        self.principal_spin.setRange(0, 1_000_000_000)
        self.principal_spin.setDecimals(2)
        self.principal_spin.setValue(principal)

        self.currency_edit = QLineEdit(currency)

        self.has_due_date_check = QCheckBox("Has due date")
        self.has_due_date_check.setChecked(due_date is not None)
        self.due_date_edit = QDateEdit(QDate(due_date or dt.date.today()))
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setEnabled(due_date is not None)
        self.has_due_date_check.toggled.connect(self.due_date_edit.setEnabled)

        self.status_combo = QComboBox()
        self.status_combo.addItems(STATUSES)
        self.status_combo.setCurrentText(status)

        form = QFormLayout()
        form.addRow("Counterparty", self.counterparty_edit)
        form.addRow("Direction", self.direction_combo)
        form.addRow("Principal", self.principal_spin)
        form.addRow("Currency", self.currency_edit)
        form.addRow(self.has_due_date_check, self.due_date_edit)
        form.addRow("Status", self.status_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @property
    def counterparty(self) -> str:
        return self.counterparty_edit.text().strip()

    @property
    def direction(self) -> str:
        return self.direction_combo.currentText()

    @property
    def principal(self) -> float:
        return self.principal_spin.value()

    @property
    def currency(self) -> str:
        return self.currency_edit.text().strip().upper()

    @property
    def due_date(self) -> dt.date | None:
        return self.due_date_edit.date().toPython() if self.has_due_date_check.isChecked() else None

    @property
    def status(self) -> str:
        return self.status_combo.currentText()
