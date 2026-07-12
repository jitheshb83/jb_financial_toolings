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


class ExchangeRateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exchange Rate")
        self.setMinimumWidth(320)

        self.from_edit = QLineEdit()
        self.from_edit.setPlaceholderText("e.g. EUR")
        self.to_edit = QLineEdit()
        self.to_edit.setPlaceholderText("e.g. USD")

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0.000001, 1_000_000)
        self.rate_spin.setDecimals(6)
        self.rate_spin.setValue(1.0)

        self.date_edit = QDateEdit(QDate(dt.date.today()))
        self.date_edit.setCalendarPopup(True)

        form = QFormLayout()
        form.addRow("From currency", self.from_edit)
        form.addRow("To currency", self.to_edit)
        form.addRow("Rate (1 From = ? To)", self.rate_spin)
        form.addRow("Date", self.date_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @property
    def from_currency(self) -> str:
        return self.from_edit.text().strip().upper()

    @property
    def to_currency(self) -> str:
        return self.to_edit.text().strip().upper()

    @property
    def rate(self) -> float:
        return self.rate_spin.value()

    @property
    def date(self) -> dt.date:
        return self.date_edit.date().toPython()
