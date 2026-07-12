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
    QVBoxLayout,
)


class FDDialog(QDialog):
    def __init__(
        self,
        parent=None,
        name: str = "",
        principal: float = 0.0,
        interest_rate: float = 0.0,
        currency: str = "USD",
        start_date: dt.date | None = None,
        maturity_date: dt.date | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Fixed Deposit")
        self.setMinimumWidth(340)

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

        today = dt.date.today()
        self.start_date_edit = QDateEdit(QDate(start_date or today))
        self.start_date_edit.setCalendarPopup(True)

        self.maturity_date_edit = QDateEdit(QDate(maturity_date or today))
        self.maturity_date_edit.setCalendarPopup(True)

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Principal", self.principal_spin)
        form.addRow("Interest rate", self.rate_spin)
        form.addRow("Currency", self.currency_edit)
        form.addRow("Start date", self.start_date_edit)
        form.addRow("Maturity date", self.maturity_date_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if self.maturity_date_edit.date() <= self.start_date_edit.date():
            self.maturity_date_edit.setFocus()
            return
        self.accept()

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
    def maturity_date(self) -> dt.date:
        return self.maturity_date_edit.date().toPython()
