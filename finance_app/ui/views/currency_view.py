from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from finance_app.services.currency_service import CurrencyService
from finance_app.ui.dialogs.exchange_rate_dialog import ExchangeRateDialog
from finance_app.ui.icons import icon

COLUMNS = ["Pair", "Rate", "Date"]


class CurrencyView(QWidget):
    def __init__(self, currency_service: CurrencyService, on_activity=None, parent=None):
        super().__init__(parent)
        self.currency = currency_service
        self._on_activity = on_activity or (lambda: None)
        self._rates_cache = []

        self.base_currency_edit = QLineEdit(self.currency.get_base_currency())
        set_base_btn = QPushButton(icon("currency"), "Set base currency")
        set_base_btn.clicked.connect(self._set_base_currency)
        base_row = QHBoxLayout()
        base_row.addWidget(QLabel("Base currency"))
        base_row.addWidget(self.base_currency_edit)
        base_row.addWidget(set_base_btn)
        base_row.addStretch()

        add_btn = QPushButton(icon("add"), "Add Rate")
        delete_btn = QPushButton(icon("delete"), "Delete Rate")
        add_btn.clicked.connect(self._add_rate)
        delete_btn.clicked.connect(self._delete_selected)
        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        hint = QLabel(
            "Rates are used for currency conversion across the app (e.g. combined portfolio "
            "totals). Only the most recent rate for a pair is used; either direction "
            "(EUR→USD or USD→EUR) works for conversion."
        )
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(base_row)
        layout.addWidget(hint)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        self.refresh()

    def refresh(self) -> None:
        self.base_currency_edit.setText(self.currency.get_base_currency())
        self._rates_cache = self.currency.list_rates()
        self.table.setRowCount(len(self._rates_cache))
        for row, rate in enumerate(self._rates_cache):
            self.table.setItem(row, 0, QTableWidgetItem(rate.currency_pair.replace("_", " → ")))
            self.table.setItem(row, 1, QTableWidgetItem(f"{rate.rate:.6f}"))
            self.table.setItem(row, 2, QTableWidgetItem(rate.date.isoformat()))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, rate.id)

    def _set_base_currency(self) -> None:
        code = self.base_currency_edit.text().strip().upper()
        if not code:
            QMessageBox.warning(self, "Missing currency", "Enter a currency code.")
            return
        self.currency.set_base_currency(code)
        self._on_activity()
        self.refresh()

    def _add_rate(self) -> None:
        dialog = ExchangeRateDialog(self)
        if dialog.exec():
            if not dialog.from_currency or not dialog.to_currency:
                QMessageBox.warning(self, "Missing info", "Both currencies are required.")
                return
            self.currency.set_rate(dialog.from_currency, dialog.to_currency, dialog.rate, dialog.date)
            self._on_activity()
            self.refresh()

    def _delete_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        rate_id = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Delete rate", "Delete this exchange rate?") == QMessageBox.StandardButton.Yes:
            self.currency.delete_rate(rate_id)
            self._on_activity()
            self.refresh()
