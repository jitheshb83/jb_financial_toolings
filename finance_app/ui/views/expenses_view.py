from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from finance_app.services.expense_service import ExpenseService
from finance_app.ui.dialogs.account_dialog import AccountDialog
from finance_app.ui.dialogs.transaction_dialog import TransactionDialog
from finance_app.ui.icons import icon

COLUMNS = ["Date", "Account", "Category", "Amount", "Currency", "Recurring", "Note"]

ALL_ACCOUNTS = "All accounts"
ALL_CATEGORIES = "All categories"


class ExpensesView(QWidget):
    def __init__(self, expense_service: ExpenseService, on_activity=None, parent=None):
        super().__init__(parent)
        self.expenses = expense_service
        self._on_activity = on_activity or (lambda: None)
        self._transactions = []

        self.account_filter = QComboBox()
        self.category_filter = QComboBox()
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate(2000, 1, 1))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())

        self.account_filter.currentIndexChanged.connect(self.refresh)
        self.category_filter.currentIndexChanged.connect(self.refresh)
        self.date_from.dateChanged.connect(self.refresh)
        self.date_to.dateChanged.connect(self.refresh)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Account"))
        filter_row.addWidget(self.account_filter)
        filter_row.addWidget(QLabel("Category"))
        filter_row.addWidget(self.category_filter)
        filter_row.addWidget(QLabel("From"))
        filter_row.addWidget(self.date_from)
        filter_row.addWidget(QLabel("To"))
        filter_row.addWidget(self.date_to)
        filter_row.addStretch()

        add_account_btn = QPushButton(icon("add"), "New Account")
        add_btn = QPushButton(icon("add"), "Add Transaction")
        edit_btn = QPushButton(icon("edit"), "Edit")
        delete_btn = QPushButton(icon("delete"), "Delete")
        add_account_btn.clicked.connect(self._add_account)
        add_btn.clicked.connect(self._add_transaction)
        edit_btn.clicked.connect(self._edit_selected)
        delete_btn.clicked.connect(self._delete_selected)

        btn_row = QHBoxLayout()
        btn_row.addWidget(add_account_btn)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._edit_selected)

        layout = QVBoxLayout(self)
        layout.addLayout(filter_row)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        self._reload_accounts()
        self._reload_categories()
        self.refresh()

    def _reload_accounts(self) -> None:
        current = self.account_filter.currentData()
        self.account_filter.blockSignals(True)
        self.account_filter.clear()
        self.account_filter.addItem(ALL_ACCOUNTS, None)
        for acc in self.expenses.list_accounts():
            self.account_filter.addItem(f"{acc.name} ({acc.currency})", acc.id)
        idx = self.account_filter.findData(current)
        self.account_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.account_filter.blockSignals(False)

    def _reload_categories(self) -> None:
        current = self.category_filter.currentData()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem(ALL_CATEGORIES, None)
        for cat in self.expenses.list_categories():
            self.category_filter.addItem(cat, cat)
        idx = self.category_filter.findData(current)
        self.category_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.category_filter.blockSignals(False)

    def _account_tuples(self) -> list[tuple[int, str, str]]:
        return [(a.id, a.name, a.currency) for a in self.expenses.list_accounts()]

    def refresh(self) -> None:
        account_id = self.account_filter.currentData()
        category = self.category_filter.currentData()
        date_from = self.date_from.date().toPython()
        date_to = self.date_to.date().toPython()

        self._transactions = self.expenses.list_transactions(
            account_id=account_id,
            category=category,
            date_from=date_from,
            date_to=date_to,
        )
        accounts_by_id = {a.id: a for a in self.expenses.list_accounts()}
        self.table.setRowCount(len(self._transactions))
        for row, txn in enumerate(self._transactions):
            account = accounts_by_id.get(txn.account_id)
            values = [
                txn.date.isoformat(),
                account.name if account else "?",
                txn.category,
                f"{txn.amount:,.2f}",
                txn.currency,
                "Yes" if txn.is_recurring else "",
                txn.note or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.table.setItem(row, col, item)
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, txn.id)

    def _selected_txn_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _add_account(self) -> None:
        dialog = AccountDialog(self)
        if dialog.exec():
            if not dialog.name or not dialog.currency:
                QMessageBox.warning(self, "Missing info", "Name and currency are required.")
                return
            self.expenses.create_account(dialog.name, dialog.type, dialog.currency)
            self._on_activity()
            self._reload_accounts()

    def _add_transaction(self) -> None:
        accounts = self._account_tuples()
        if not accounts:
            QMessageBox.information(self, "No accounts", "Create an account first.")
            return
        dialog = TransactionDialog(self, accounts=accounts, categories=self.expenses.list_categories())
        if dialog.exec():
            if dialog.account_id is None or not dialog.category or not dialog.currency:
                QMessageBox.warning(self, "Missing info", "Account, category, and currency are required.")
                return
            self.expenses.create_transaction(
                account_id=dialog.account_id,
                date=dialog.date,
                category=dialog.category,
                amount=dialog.amount,
                currency=dialog.currency,
                is_recurring=dialog.is_recurring,
                recurrence_rule=dialog.recurrence_rule,
                note=dialog.note,
            )
            self._on_activity()
            self._reload_categories()
            self.refresh()

    def _edit_selected(self) -> None:
        txn_id = self._selected_txn_id()
        if txn_id is None:
            return
        txn = next(t for t in self._transactions if t.id == txn_id)
        accounts = self._account_tuples()
        dialog = TransactionDialog(
            self,
            accounts=accounts,
            categories=self.expenses.list_categories(),
            date=txn.date,
            account_id=txn.account_id,
            category=txn.category,
            amount=txn.amount,
            currency=txn.currency,
            is_recurring=txn.is_recurring,
            recurrence_rule=txn.recurrence_rule or "",
            note=txn.note or "",
        )
        if dialog.exec():
            self.expenses.update_transaction(
                txn_id,
                account_id=dialog.account_id,
                date=dialog.date,
                category=dialog.category,
                amount=dialog.amount,
                currency=dialog.currency,
                is_recurring=dialog.is_recurring,
                recurrence_rule=dialog.recurrence_rule,
                note=dialog.note,
            )
            self._on_activity()
            self._reload_categories()
            self.refresh()

    def _delete_selected(self) -> None:
        txn_id = self._selected_txn_id()
        if txn_id is None:
            return
        if (
            QMessageBox.question(self, "Delete transaction", "Delete this transaction?")
            == QMessageBox.StandardButton.Yes
        ):
            self.expenses.delete_transaction(txn_id)
            self._on_activity()
            self.refresh()
