from __future__ import annotations

from collections import defaultdict

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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from finance_app.services.currency_service import CurrencyService
from finance_app.services.fd_service import FDService, maturity_value
from finance_app.services.investment_service import InvestmentService, gain_loss, market_value
from finance_app.ui.dialogs.fd_dialog import FDDialog
from finance_app.ui.dialogs.investment_dialog import InvestmentDialog
from finance_app.ui.dialogs.other_investment_dialog import OtherInvestmentDialog
from finance_app.ui.icons import icon

INVESTMENT_COLUMNS = ["Name", "Type", "Currency", "Units", "Buy Price", "Current Price", "Market Value", "Gain/Loss"]
FD_COLUMNS = ["Name", "Currency", "Principal", "Rate", "Start", "Maturity", "Est. Maturity Value"]
OTHER_COLUMNS = ["Name", "Type", "Currency", "Value", "Note"]


class InvestmentsView(QWidget):
    def __init__(
        self,
        investment_service: InvestmentService,
        fd_service: FDService,
        currency_service: CurrencyService,
        on_activity=None,
        parent=None,
    ):
        super().__init__(parent)
        self.investments = investment_service
        self.fds = fd_service
        self.currency = currency_service
        self._on_activity = on_activity or (lambda: None)
        self._investments_cache = []
        self._fds_cache = []
        self._other_cache = []

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)

        self.sub_tabs = QTabWidget()
        self.sub_tabs.addTab(self._build_investments_tab(), "Stocks & Funds")
        self.sub_tabs.addTab(self._build_fds_tab(), "Fixed Deposits")
        self.sub_tabs.addTab(self._build_other_tab(), "Other Investments")

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.sub_tabs)

        self.refresh()

    # -- stocks/funds sub-tab --------------------------------------------
    def _build_investments_tab(self) -> QWidget:
        widget = QWidget()
        add_btn = QPushButton(icon("add"), "Add")
        edit_btn = QPushButton(icon("edit"), "Edit")
        delete_btn = QPushButton(icon("delete"), "Delete")
        add_btn.clicked.connect(self._add_investment)
        edit_btn.clicked.connect(self._edit_investment)
        delete_btn.clicked.connect(self._delete_investment)
        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()

        self.investment_table = QTableWidget(0, len(INVESTMENT_COLUMNS))
        self.investment_table.setHorizontalHeaderLabels(INVESTMENT_COLUMNS)
        self.investment_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.investment_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.investment_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.investment_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.investment_table.doubleClicked.connect(self._edit_investment)

        layout = QVBoxLayout(widget)
        layout.addLayout(btn_row)
        layout.addWidget(self.investment_table)
        return widget

    def _selected_investment_id(self) -> int | None:
        rows = self.investment_table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.investment_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _add_investment(self) -> None:
        dialog = InvestmentDialog(self)
        if dialog.exec():
            if not dialog.name or not dialog.currency:
                QMessageBox.warning(self, "Missing info", "Name and currency are required.")
                return
            self.investments.create_investment(
                dialog.name, dialog.type, dialog.currency, dialog.units, dialog.buy_price, dialog.current_price
            )
            self._on_activity()
            self.refresh()

    def _edit_investment(self) -> None:
        inv_id = self._selected_investment_id()
        if inv_id is None:
            return
        inv = next(i for i in self._investments_cache if i.id == inv_id)
        dialog = InvestmentDialog(
            self,
            name=inv.name,
            type=inv.type,
            currency=inv.currency,
            units=inv.units,
            buy_price=inv.buy_price,
            current_price=inv.current_price,
        )
        if dialog.exec():
            self.investments.update_investment(
                inv_id, dialog.name, dialog.type, dialog.currency, dialog.units, dialog.buy_price, dialog.current_price
            )
            self._on_activity()
            self.refresh()

    def _delete_investment(self) -> None:
        inv_id = self._selected_investment_id()
        if inv_id is None:
            return
        if QMessageBox.question(self, "Delete investment", "Delete this holding?") == QMessageBox.StandardButton.Yes:
            self.investments.delete_investment(inv_id)
            self._on_activity()
            self.refresh()

    # -- fixed deposits sub-tab ---------------------------------------
    def _build_fds_tab(self) -> QWidget:
        widget = QWidget()
        add_btn = QPushButton(icon("add"), "Add")
        edit_btn = QPushButton(icon("edit"), "Edit")
        delete_btn = QPushButton(icon("delete"), "Delete")
        add_btn.clicked.connect(self._add_fd)
        edit_btn.clicked.connect(self._edit_fd)
        delete_btn.clicked.connect(self._delete_fd)
        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()

        self.fd_table = QTableWidget(0, len(FD_COLUMNS))
        self.fd_table.setHorizontalHeaderLabels(FD_COLUMNS)
        self.fd_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.fd_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.fd_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.fd_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.fd_table.doubleClicked.connect(self._edit_fd)

        layout = QVBoxLayout(widget)
        layout.addLayout(btn_row)
        layout.addWidget(self.fd_table)
        return widget

    def _selected_fd_id(self) -> int | None:
        rows = self.fd_table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.fd_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _add_fd(self) -> None:
        dialog = FDDialog(self)
        if dialog.exec():
            if not dialog.name or not dialog.currency:
                QMessageBox.warning(self, "Missing info", "Name and currency are required.")
                return
            self.fds.create_fd(
                dialog.name, dialog.principal, dialog.interest_rate, dialog.currency, dialog.start_date, dialog.maturity_date
            )
            self._on_activity()
            self.refresh()

    def _edit_fd(self) -> None:
        fd_id = self._selected_fd_id()
        if fd_id is None:
            return
        fd = next(f for f in self._fds_cache if f.id == fd_id)
        dialog = FDDialog(
            self,
            name=fd.name,
            principal=fd.principal,
            interest_rate=fd.interest_rate,
            currency=fd.currency,
            start_date=fd.start_date,
            maturity_date=fd.maturity_date,
        )
        if dialog.exec():
            self.fds.update_fd(
                fd_id, dialog.name, dialog.principal, dialog.interest_rate, dialog.currency, dialog.start_date, dialog.maturity_date
            )
            self._on_activity()
            self.refresh()

    def _delete_fd(self) -> None:
        fd_id = self._selected_fd_id()
        if fd_id is None:
            return
        if QMessageBox.question(self, "Delete FD", "Delete this fixed deposit?") == QMessageBox.StandardButton.Yes:
            self.fds.delete_fd(fd_id)
            self._on_activity()
            self.refresh()

    # -- other investments sub-tab -------------------------------------
    def _build_other_tab(self) -> QWidget:
        widget = QWidget()
        add_btn = QPushButton(icon("add"), "Add")
        edit_btn = QPushButton(icon("edit"), "Edit")
        delete_btn = QPushButton(icon("delete"), "Delete")
        add_btn.clicked.connect(self._add_other)
        edit_btn.clicked.connect(self._edit_other)
        delete_btn.clicked.connect(self._delete_other)
        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch()

        self.other_table = QTableWidget(0, len(OTHER_COLUMNS))
        self.other_table.setHorizontalHeaderLabels(OTHER_COLUMNS)
        self.other_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.other_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.other_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.other_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.other_table.doubleClicked.connect(self._edit_other)

        layout = QVBoxLayout(widget)
        layout.addLayout(btn_row)
        layout.addWidget(self.other_table)
        return widget

    def _selected_other_id(self) -> int | None:
        rows = self.other_table.selectionModel().selectedRows()
        if not rows:
            return None
        return self.other_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def _add_other(self) -> None:
        dialog = OtherInvestmentDialog(self)
        if dialog.exec():
            if not dialog.name or not dialog.type or not dialog.currency:
                QMessageBox.warning(self, "Missing info", "Name, type, and currency are required.")
                return
            self.investments.create_other_investment(
                dialog.name, dialog.type, dialog.currency, dialog.value, dialog.note
            )
            self._on_activity()
            self.refresh()

    def _edit_other(self) -> None:
        other_id = self._selected_other_id()
        if other_id is None:
            return
        other = next(o for o in self._other_cache if o.id == other_id)
        dialog = OtherInvestmentDialog(
            self, name=other.name, type=other.type, currency=other.currency, value=other.value, note=other.note or ""
        )
        if dialog.exec():
            self.investments.update_other_investment(
                other_id, dialog.name, dialog.type, dialog.currency, dialog.value, dialog.note
            )
            self._on_activity()
            self.refresh()

    def _delete_other(self) -> None:
        other_id = self._selected_other_id()
        if other_id is None:
            return
        if QMessageBox.question(self, "Delete item", "Delete this holding?") == QMessageBox.StandardButton.Yes:
            self.investments.delete_other_investment(other_id)
            self._on_activity()
            self.refresh()

    # -- shared refresh ---------------------------------------------------
    def refresh(self) -> None:
        self._investments_cache = self.investments.list_investments()
        self.investment_table.setRowCount(len(self._investments_cache))
        for row, inv in enumerate(self._investments_cache):
            values = [
                inv.name,
                inv.type,
                inv.currency,
                f"{inv.units:,.4f}",
                f"{inv.buy_price:,.4f}",
                f"{inv.current_price:,.4f}",
                f"{market_value(inv):,.2f}",
                f"{gain_loss(inv):,.2f}",
            ]
            for col, value in enumerate(values):
                self.investment_table.setItem(row, col, QTableWidgetItem(value))
            self.investment_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, inv.id)

        self._fds_cache = self.fds.list_fds()
        self.fd_table.setRowCount(len(self._fds_cache))
        for row, fd in enumerate(self._fds_cache):
            values = [
                fd.name,
                fd.currency,
                f"{fd.principal:,.2f}",
                f"{fd.interest_rate:.2f}%",
                fd.start_date.isoformat(),
                fd.maturity_date.isoformat(),
                f"{maturity_value(fd):,.2f}",
            ]
            for col, value in enumerate(values):
                self.fd_table.setItem(row, col, QTableWidgetItem(value))
            self.fd_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, fd.id)

        self._other_cache = self.investments.list_other_investments()
        self.other_table.setRowCount(len(self._other_cache))
        for row, other in enumerate(self._other_cache):
            values = [other.name, other.type, other.currency, f"{other.value:,.2f}", other.note or ""]
            for col, value in enumerate(values):
                self.other_table.setItem(row, col, QTableWidgetItem(value))
            self.other_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, other.id)

        self._update_summary()

    def _update_summary(self) -> None:
        totals: dict[str, float] = defaultdict(float)
        for currency, value in self.investments.rollup_by_currency().items():
            totals[currency] += value
        for currency, value in self.fds.rollup_by_currency().items():
            totals[currency] += value
        if not totals:
            self.summary_label.setText("No holdings yet.")
            return
        parts = [f"{currency} {amount:,.2f}" for currency, amount in sorted(totals.items())]
        text = "Portfolio value by currency (stocks/funds + FD principal + other): " + "  |  ".join(parts)

        base = self.currency.get_base_currency()
        combined = 0.0
        missing_rates = []
        for currency, amount in totals.items():
            converted = self.currency.try_convert(amount, currency, base)
            if converted is None:
                missing_rates.append(currency)
            else:
                combined += converted
        if missing_rates:
            text += f"\nAdd exchange rates for {', '.join(sorted(missing_rates))} → {base} to see a combined total."
        else:
            text += f"\nCombined total: {base} {combined:,.2f}"
        self.summary_label.setText(text)
