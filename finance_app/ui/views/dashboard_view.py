from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from finance_app.services.report_service import ReportService
from finance_app.ui.icons import icon
from finance_app.ui.widgets.chart_canvas import ChartCanvas


class DashboardView(QWidget):
    def __init__(self, report_service: ReportService, on_activity=None, parent=None):
        super().__init__(parent)
        self.reports = report_service
        self._on_activity = on_activity or (lambda: None)

        refresh_btn = QPushButton(icon("refresh"), "Refresh Dashboard")
        refresh_btn.clicked.connect(self.refresh)

        self.extra_spin = QDoubleSpinBox()
        self.extra_spin.setRange(0, 1_000_000_000)
        self.extra_spin.setDecimals(2)
        self.extra_spin.setPrefix("Debt extra/mo: ")
        self.extra_spin.valueChanged.connect(self._refresh_debt_chart)

        self.method_combo = QComboBox()
        self.method_combo.addItems(["avalanche", "snowball"])
        self.method_combo.currentTextChanged.connect(self._refresh_debt_chart)

        controls = QHBoxLayout()
        controls.addWidget(refresh_btn)
        controls.addWidget(self.extra_spin)
        controls.addWidget(self.method_combo)
        controls.addStretch()

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)

        self.net_worth_chart = ChartCanvas("Net Worth Over Time")
        self.expense_chart = ChartCanvas("Expense Breakdown")
        self.debt_chart = ChartCanvas("Debt Payoff Timeline")
        self.allocation_chart = ChartCanvas("Investment Allocation")

        grid = QGridLayout()
        grid.addWidget(self.net_worth_chart, 0, 0)
        grid.addWidget(self.expense_chart, 0, 1)
        grid.addWidget(self.debt_chart, 1, 0)
        grid.addWidget(self.allocation_chart, 1, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.warning_label)
        layout.addLayout(grid)

        self.refresh()

    def refresh(self) -> None:
        self.reports.record_snapshot_if_needed()
        self._on_activity()
        warnings = set()

        self._draw_net_worth_chart()
        warnings |= set(self._draw_expense_chart())
        warnings |= set(self._draw_allocation_chart())
        self._refresh_debt_chart()

        base = self.reports.currency.get_base_currency()
        if warnings:
            self.warning_label.setText(
                f"Some amounts couldn't be converted to {base} — add exchange rates for: "
                + ", ".join(sorted(warnings))
            )
        else:
            self.warning_label.setText("")

    def _draw_net_worth_chart(self) -> None:
        history = self.reports.net_worth_history()
        base = self.reports.currency.get_base_currency()
        if not history:
            self.net_worth_chart.show_empty("No snapshots yet.")
            return
        dates = [d for d, _ in history]
        values = [v for _, v in history]
        ax = self.net_worth_chart.clear()
        ax.plot(dates, values, marker="o")
        ax.set_ylabel(base)
        self.net_worth_chart.figure.autofmt_xdate()
        self.net_worth_chart.draw()

    def _draw_expense_chart(self) -> list[str]:
        breakdown, skipped = self.reports.expense_breakdown()
        if not breakdown:
            self.expense_chart.show_empty("No expenses recorded yet.")
            return skipped
        ax = self.expense_chart.clear()
        labels = list(breakdown.keys())
        values = list(breakdown.values())
        ax.pie(values, labels=labels, autopct="%1.0f%%")
        self.expense_chart.draw()
        return skipped

    def _draw_allocation_chart(self) -> list[str]:
        allocation, skipped = self.reports.investment_allocation()
        if not allocation:
            self.allocation_chart.show_empty("No holdings yet.")
            return skipped
        ax = self.allocation_chart.clear()
        labels = list(allocation.keys())
        values = list(allocation.values())
        ax.pie(values, labels=labels, autopct="%1.0f%%")
        self.allocation_chart.draw()
        return skipped

    def _refresh_debt_chart(self) -> None:
        plan = self.reports.debt_payoff_timeline(self.extra_spin.value(), self.method_combo.currentText())
        if plan is None:
            self.debt_chart.show_empty("No debts recorded yet.")
            return
        if not plan.feasible:
            self.debt_chart.show_empty("This budget won't pay off these debts — increase extra/mo.")
            return
        ax = self.debt_chart.clear()
        names = [r.name for r in plan.per_debt]
        months = [r.months_to_payoff for r in plan.per_debt]
        ax.barh(names, months)
        ax.set_xlabel("Months to payoff")
        self.debt_chart.figure.tight_layout()
        self.debt_chart.draw()
