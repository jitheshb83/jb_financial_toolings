from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from finance_app.services.debt_service import DebtService, calculate_payoff_plan
from finance_app.ui.dialogs.debt_dialog import DebtDialog
from finance_app.ui.icons import icon

DEBT_COLUMNS = ["Name", "Principal", "Rate", "Currency", "Term", "Min. Payment"]
PLAN_COLUMNS = ["Debt", "Payoff Date", "Months", "Interest Paid"]


class DebtView(QWidget):
    def __init__(self, debt_service: DebtService, on_activity=None, parent=None):
        super().__init__(parent)
        self.debts = debt_service
        self._on_activity = on_activity or (lambda: None)
        self._debts_cache = []

        add_btn = QPushButton(icon("add"), "Add Debt")
        edit_btn = QPushButton(icon("edit"), "Edit")
        delete_btn = QPushButton(icon("delete"), "Delete")
        add_btn.clicked.connect(self._add_debt)
        edit_btn.clicked.connect(self._edit_selected)
        delete_btn.clicked.connect(self._delete_selected)

        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()

        self.debt_table = QTableWidget(0, len(DEBT_COLUMNS))
        self.debt_table.setHorizontalHeaderLabels(DEBT_COLUMNS)
        self.debt_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.debt_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.debt_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.debt_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.debt_table.doubleClicked.connect(self._edit_selected)

        # -- payoff plan panel --------------------------------------------
        self.extra_spin = QDoubleSpinBox()
        self.extra_spin.setRange(0, 1_000_000_000)
        self.extra_spin.setDecimals(2)
        self.extra_spin.setPrefix("Extra/mo: ")

        self.snowball_radio = QRadioButton("Snowball (smallest balance first)")
        self.avalanche_radio = QRadioButton("Avalanche (highest rate first)")
        self.avalanche_radio.setChecked(True)

        calculate_btn = QPushButton(icon("calculate"), "Calculate Payoff Plan")
        calculate_btn.clicked.connect(self._calculate)

        controls_row = QHBoxLayout()
        controls_row.addWidget(self.extra_spin)
        controls_row.addWidget(self.snowball_radio)
        controls_row.addWidget(self.avalanche_radio)
        controls_row.addWidget(calculate_btn)
        controls_row.addStretch()

        self.summary_label = QLabel("Add debts, then calculate a payoff plan.")
        self.summary_label.setWordWrap(True)

        self.plan_table = QTableWidget(0, len(PLAN_COLUMNS))
        self.plan_table.setHorizontalHeaderLabels(PLAN_COLUMNS)
        self.plan_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.plan_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        plan_box = QGroupBox("Payoff Plan")
        plan_layout = QVBoxLayout(plan_box)
        plan_layout.addLayout(controls_row)
        plan_layout.addWidget(self.summary_label)
        plan_layout.addWidget(self.plan_table)

        layout = QVBoxLayout(self)
        layout.addLayout(btn_row)
        layout.addWidget(self.debt_table)
        layout.addWidget(plan_box)

        self.refresh()

    def refresh(self) -> None:
        self._debts_cache = self.debts.list_debts()
        self.debt_table.setRowCount(len(self._debts_cache))
        for row, debt in enumerate(self._debts_cache):
            values = [
                debt.name,
                f"{debt.principal:,.2f}",
                f"{debt.interest_rate:.2f}%",
                debt.currency,
                f"{debt.term_months} mo",
                f"{debt.minimum_payment:,.2f}",
            ]
            for col, value in enumerate(values):
                self.debt_table.setItem(row, col, QTableWidgetItem(value))
            self.debt_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, debt.id)
        self.plan_table.setRowCount(0)
        self.summary_label.setText("Add debts, then calculate a payoff plan.")

    def _selected_debt_id(self) -> int | None:
        rows = self.debt_table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.debt_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _add_debt(self) -> None:
        dialog = DebtDialog(self)
        if dialog.exec():
            if not dialog.name or not dialog.currency:
                QMessageBox.warning(self, "Missing info", "Name and currency are required.")
                return
            self.debts.create_debt(
                name=dialog.name,
                principal=dialog.principal,
                interest_rate=dialog.interest_rate,
                currency=dialog.currency,
                start_date=dialog.start_date,
                term_months=dialog.term_months,
                minimum_payment=dialog.minimum_payment,
            )
            self._on_activity()
            self.refresh()

    def _edit_selected(self) -> None:
        debt_id = self._selected_debt_id()
        if debt_id is None:
            return
        debt = next(d for d in self._debts_cache if d.id == debt_id)
        dialog = DebtDialog(
            self,
            name=debt.name,
            principal=debt.principal,
            interest_rate=debt.interest_rate,
            currency=debt.currency,
            start_date=debt.start_date,
            term_months=debt.term_months,
            minimum_payment=debt.minimum_payment,
        )
        if dialog.exec():
            self.debts.update_debt(
                debt_id,
                name=dialog.name,
                principal=dialog.principal,
                interest_rate=dialog.interest_rate,
                currency=dialog.currency,
                start_date=dialog.start_date,
                term_months=dialog.term_months,
                minimum_payment=dialog.minimum_payment,
            )
            self._on_activity()
            self.refresh()

    def _delete_selected(self) -> None:
        debt_id = self._selected_debt_id()
        if debt_id is None:
            return
        if (
            QMessageBox.question(self, "Delete debt", "Delete this debt?")
            == QMessageBox.StandardButton.Yes
        ):
            self.debts.delete_debt(debt_id)
            self._on_activity()
            self.refresh()

    def _calculate(self) -> None:
        if not self._debts_cache:
            QMessageBox.information(self, "No debts", "Add at least one debt first.")
            return
        method = "snowball" if self.snowball_radio.isChecked() else "avalanche"
        plan = calculate_payoff_plan(
            self._debts_cache, extra_monthly_payment=self.extra_spin.value(), method=method
        )
        other_method = "avalanche" if method == "snowball" else "snowball"
        other_plan = calculate_payoff_plan(
            self._debts_cache, extra_monthly_payment=self.extra_spin.value(), method=other_method
        )

        if not plan.feasible:
            self.summary_label.setText(
                "This budget doesn't cover accruing interest — these debts won't be paid off. "
                "Increase the extra monthly payment."
            )
            self.plan_table.setRowCount(0)
            return

        self.summary_label.setText(
            f"{method.title()}: paid off in {plan.total_months} months "
            f"(by {plan.total_payoff_date}), total interest "
            f"{plan.total_interest_paid:,.2f}.  "
            f"{other_method.title()} comparison: "
            + (
                f"{other_plan.total_months} months, "
                f"total interest {other_plan.total_interest_paid:,.2f}."
                if other_plan.feasible
                else "not feasible at this budget."
            )
        )

        self.plan_table.setRowCount(len(plan.per_debt))
        for row, result in enumerate(plan.per_debt):
            values = [
                result.name,
                result.payoff_date.isoformat() if result.payoff_date else "—",
                str(result.months_to_payoff) if result.months_to_payoff else "—",
                f"{result.total_interest_paid:,.2f}",
            ]
            for col, value in enumerate(values):
                self.plan_table.setItem(row, col, QTableWidgetItem(value))
