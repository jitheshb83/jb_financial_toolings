from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)


class DebtDialog(QDialog):
    def __init__(
        self,
        parent=None,
        name: str = "",
        principal: float = 0.0,
        interest_rate: float = 0.0,
        currency: str = "USD",
        start_date: dt.date | None = None,
        term_months: int = 12,
        minimum_payment: float = 0.0,
    ):
        super().__init__(parent)
        self.setWindowTitle("Debt / Loan")
        self.setMinimumWidth(360)

        self.name_edit = QLineEdit(name)

        self.principal_spin = QDoubleSpinBox()
        self.principal_spin.setRange(0, 1_000_000_000)
        self.principal_spin.setDecimals(2)
        self.principal_spin.setValue(principal)

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0, 100)
        self.rate_spin.setDecimals(2)
        self.rate_spin.setSuffix(" %")
        self.rate_spin.setValue(interest_rate)

        self.currency_edit = QLineEdit(currency)

        self.start_date_edit = QDateEdit(QDate(start_date or dt.date.today()))
        self.start_date_edit.setCalendarPopup(True)

        self.term_spin = QSpinBox()
        self.term_spin.setRange(1, 600)
        self.term_spin.setSuffix(" months")
        self.term_spin.setValue(term_months)

        self.minimum_payment_spin = QDoubleSpinBox()
        self.minimum_payment_spin.setRange(0, 1_000_000_000)
        self.minimum_payment_spin.setDecimals(2)
        self.minimum_payment_spin.setValue(minimum_payment)

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Principal", self.principal_spin)
        form.addRow("Interest rate", self.rate_spin)
        form.addRow("Currency", self.currency_edit)
        form.addRow("Start date", self.start_date_edit)
        form.addRow("Term", self.term_spin)
        form.addRow("Minimum payment", self.minimum_payment_spin)

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
    def principal(self) -> float:
        return self.principal_spin.value()

    @property
    def interest_rate(self) -> float:
        return self.rate_spin.value()

    @property
    def currency(self) -> str:
        return self.currency_edit.text().strip().upper()

    @property
    def start_date(self) -> dt.date:
        return self.start_date_edit.date().toPython()

    @property
    def term_months(self) -> int:
        return self.term_spin.value()

    @property
    def minimum_payment(self) -> float:
        return self.minimum_payment_spin.value()
