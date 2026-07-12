from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from finance_app.services.borrowing_service import BorrowingService
from finance_app.services.currency_service import CurrencyService
from finance_app.ui.dialogs.borrowing_dialog import BorrowingDialog
from finance_app.ui.icons import icon

COLUMNS = ["Counterparty", "Direction", "Principal", "Currency", "Due Date", "Status"]


class BorrowingsView(QWidget):
    def __init__(
        self,
        borrowing_service: BorrowingService,
        currency_service: CurrencyService,
        on_activity=None,
        parent=None,
    ):
        super().__init__(parent)
        self.borrowings = borrowing_service
        self.currency = currency_service
        self._on_activity = on_activity or (lambda: None)
        self._cache = []

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)

        add_btn = QPushButton(icon("add"), "Add")
        edit_btn = QPushButton(icon("edit"), "Edit")
        settle_btn = QPushButton(icon("settle"), "Mark Settled")
        delete_btn = QPushButton(icon("delete"), "Delete")
        add_btn.clicked.connect(self._add_borrowing)
        edit_btn.clicked.connect(self._edit_selected)
        settle_btn.clicked.connect(self._settle_selected)
        delete_btn.clicked.connect(self._delete_selected)

        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(settle_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._edit_selected)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        self.refresh()

    def refresh(self) -> None:
        self._cache = self.borrowings.list_borrowings()
        self.table.setRowCount(len(self._cache))
        for row, b in enumerate(self._cache):
            values = [
                b.counterparty,
                b.direction,
                f"{b.principal:,.2f}",
                b.currency,
                b.due_date.isoformat() if b.due_date else "—",
                b.status,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, b.id)
        self._update_summary()

    def _update_summary(self) -> None:
        totals = self.borrowings.outstanding_rollup_by_currency()
        if not totals:
            self.summary_label.setText("No outstanding borrowings.")
            return
        parts = []
        for currency, amounts in sorted(totals.items()):
            parts.append(
                f"{currency}: owed to you {amounts['lent']:,.2f}, you owe {amounts['owed']:,.2f}"
            )
        text = "Outstanding (pending only) — " + "  |  ".join(parts)

        base = self.currency.get_base_currency()
        net_combined = 0.0
        missing_rates = []
        for currency, amounts in totals.items():
            net = amounts["lent"] - amounts["owed"]
            converted = self.currency.try_convert(net, currency, base)
            if converted is None:
                missing_rates.append(currency)
            else:
                net_combined += converted
        if missing_rates:
            text += f"\nAdd exchange rates for {', '.join(sorted(missing_rates))} → {base} to see a combined net position."
        else:
            text += f"\nNet position in {base}: {net_combined:,.2f}"
        self.summary_label.setText(text)

    def _selected_id(self) -> int | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _add_borrowing(self) -> None:
        dialog = BorrowingDialog(self)
        if dialog.exec():
            if not dialog.counterparty or not dialog.currency:
                QMessageBox.warning(self, "Missing info", "Counterparty and currency are required.")
                return
            self.borrowings.create_borrowing(
                dialog.counterparty, dialog.direction, dialog.principal, dialog.currency, dialog.due_date, dialog.status
            )
            self._on_activity()
            self.refresh()

    def _edit_selected(self) -> None:
        b_id = self._selected_id()
        if b_id is None:
            return
        b = next(x for x in self._cache if x.id == b_id)
        dialog = BorrowingDialog(
            self,
            counterparty=b.counterparty,
            direction=b.direction,
            principal=b.principal,
            currency=b.currency,
            due_date=b.due_date,
            status=b.status,
        )
        if dialog.exec():
            self.borrowings.update_borrowing(
                b_id, dialog.counterparty, dialog.direction, dialog.principal, dialog.currency, dialog.due_date, dialog.status
            )
            self._on_activity()
            self.refresh()

    def _settle_selected(self) -> None:
        b_id = self._selected_id()
        if b_id is None:
            return
        self.borrowings.mark_settled(b_id)
        self._on_activity()
        self.refresh()

    def _delete_selected(self) -> None:
        b_id = self._selected_id()
        if b_id is None:
            return
        if QMessageBox.question(self, "Delete borrowing", "Delete this record?") == QMessageBox.StandardButton.Yes:
            self.borrowings.delete_borrowing(b_id)
            self._on_activity()
            self.refresh()
