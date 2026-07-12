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

RECURRENCE_OPTIONS = ["weekly", "monthly", "yearly"]


class TransactionDialog(QDialog):
    def __init__(
        self,
        parent=None,
        accounts: list[tuple[int, str, str]] | None = None,  # (id, name, currency)
        categories: list[str] | None = None,
        date: dt.date | None = None,
        account_id: int | None = None,
        category: str = "",
        amount: float = 0.0,
        currency: str = "",
        is_recurring: bool = False,
        recurrence_rule: str = "",
        note: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("Transaction")
        self.setMinimumWidth(380)
        self._accounts = accounts or []

        self.account_combo = QComboBox()
        for acc_id, name, acc_currency in self._accounts:
            self.account_combo.addItem(f"{name} ({acc_currency})", (acc_id, acc_currency))
        if account_id is not None:
            for i, (acc_id, _, _) in enumerate(self._accounts):
                if acc_id == account_id:
                    self.account_combo.setCurrentIndex(i)
                    break
        self.account_combo.currentIndexChanged.connect(self._on_account_changed)

        self.date_edit = QDateEdit(QDate(date or dt.date.today()))
        self.date_edit.setCalendarPopup(True)

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(categories or [])
        if category:
            self.category_combo.setCurrentText(category)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(-1_000_000_000, 1_000_000_000)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setValue(amount)

        self.currency_edit = QLineEdit(currency)

        self.recurring_check = QCheckBox("Recurring")
        self.recurring_check.setChecked(is_recurring)
        self.recurrence_combo = QComboBox()
        self.recurrence_combo.addItems(RECURRENCE_OPTIONS)
        if recurrence_rule in RECURRENCE_OPTIONS:
            self.recurrence_combo.setCurrentText(recurrence_rule)
        self.recurrence_combo.setEnabled(is_recurring)
        self.recurring_check.toggled.connect(self.recurrence_combo.setEnabled)

        self.note_edit = QLineEdit(note)

        form = QFormLayout()
        form.addRow("Account", self.account_combo)
        form.addRow("Date", self.date_edit)
        form.addRow("Category", self.category_combo)
        form.addRow("Amount", self.amount_spin)
        form.addRow("Currency", self.currency_edit)
        form.addRow(self.recurring_check, self.recurrence_combo)
        form.addRow("Note", self.note_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        if not currency and self._accounts:
            self._on_account_changed(self.account_combo.currentIndex())

    def _on_account_changed(self, index: int) -> None:
        if index < 0 or index >= len(self._accounts):
            return
        _, _, acc_currency = self._accounts[index]
        self.currency_edit.setText(acc_currency)

    @property
    def account_id(self) -> int | None:
        data = self.account_combo.currentData()
        return data[0] if data else None

    @property
    def date(self) -> dt.date:
        return self.date_edit.date().toPython()

    @property
    def category(self) -> str:
        return self.category_combo.currentText().strip()

    @property
    def amount(self) -> float:
        return self.amount_spin.value()

    @property
    def currency(self) -> str:
        return self.currency_edit.text().strip().upper()

    @property
    def is_recurring(self) -> bool:
        return self.recurring_check.isChecked()

    @property
    def recurrence_rule(self) -> str:
        return self.recurrence_combo.currentText()

    @property
    def note(self) -> str:
        return self.note_edit.text().strip()
