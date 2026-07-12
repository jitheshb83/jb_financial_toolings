from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTabWidget

from finance_app.data.database import DatabaseManager
from finance_app.services.borrowing_service import BorrowingService
from finance_app.services.currency_service import CurrencyService
from finance_app.services.debt_service import DebtService
from finance_app.services.expense_service import ExpenseService
from finance_app.services.fd_service import FDService
from finance_app.services.investment_service import InvestmentService
from finance_app.services.report_service import ReportService
from finance_app.services.vault_service import VaultService
from finance_app.ui.icons import icon
from finance_app.ui.views.borrowings_view import BorrowingsView
from finance_app.ui.views.currency_view import CurrencyView
from finance_app.ui.views.dashboard_view import DashboardView
from finance_app.ui.views.debt_view import DebtView
from finance_app.ui.views.expenses_view import ExpensesView
from finance_app.ui.views.investments_view import InvestmentsView
from finance_app.ui.views.vault_view import VaultView

IDLE_LOCK_SECONDS = 5 * 60


class MainWindow(QMainWindow):
    def __init__(self, db: DatabaseManager, on_locked):
        super().__init__()
        self.db = db
        self._on_locked = on_locked
        self._session = db.session()

        self.setWindowTitle("Personal Finance")
        self.resize(1000, 700)

        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(IDLE_LOCK_SECONDS * 1000)
        self._idle_timer.timeout.connect(self.lock)
        self._idle_timer.start()

        self.tabs = QTabWidget()

        currency_service = CurrencyService(self._session)

        expense_service = ExpenseService(self._session)
        self.expenses_view = ExpensesView(expense_service, on_activity=self._on_data_activity)
        self.tabs.addTab(self.expenses_view, icon("expenses"), "Expenses")

        debt_service = DebtService(self._session)
        self.debt_view = DebtView(debt_service, on_activity=self._on_data_activity)
        self.tabs.addTab(self.debt_view, icon("debts"), "Debts")

        investment_service = InvestmentService(self._session)
        fd_service = FDService(self._session)
        self.investments_view = InvestmentsView(
            investment_service, fd_service, currency_service, on_activity=self._on_data_activity
        )
        self.tabs.addTab(self.investments_view, icon("investments"), "Investments")

        borrowing_service = BorrowingService(self._session)
        self.borrowings_view = BorrowingsView(
            borrowing_service, currency_service, on_activity=self._on_data_activity
        )
        self.tabs.addTab(self.borrowings_view, icon("borrowings"), "Borrowings")

        self.currency_view = CurrencyView(currency_service, on_activity=self._on_data_activity)
        self.tabs.addTab(self.currency_view, icon("currency"), "Currency")

        vault_service = VaultService(self._session, db.vault_key)
        self.vault_view = VaultView(vault_service, on_activity=self._on_data_activity)
        self.tabs.addTab(self.vault_view, icon("vault"), "Vault")

        # Built last since its first refresh() fires _on_data_activity, which
        # touches investments_view/borrowings_view above.
        report_service = ReportService(self._session, currency_service)
        self.dashboard_view = DashboardView(report_service, on_activity=self._on_data_activity)
        self.tabs.insertTab(0, self.dashboard_view, icon("dashboard"), "Dashboard")
        self.tabs.setCurrentIndex(0)

        self.setCentralWidget(self.tabs)
        self.setWindowIcon(icon("dashboard"))

        lock_action = self.menuBar().addMenu("&File").addAction(icon("lock"), "Lock now")
        lock_action.triggered.connect(self.lock)

        self.statusBar().showMessage(f"Unlocked: {self.db.encrypted_path}")

    def add_module_tab(self, widget, title: str) -> None:
        self.tabs.addTab(widget, title)

    def reset_idle_timer(self) -> None:
        self._idle_timer.start()

    def _on_data_activity(self) -> None:
        self.reset_idle_timer()
        self.db.save()
        # Currency rate/base changes affect these rollups even when the
        # activity originated in a different tab.
        self.investments_view.refresh()
        self.borrowings_view.refresh()

    def lock(self) -> None:
        self._idle_timer.stop()
        self._session.close()
        try:
            self.db.lock()
        except Exception as exc:  # pragma: no cover - defensive UI feedback
            QMessageBox.critical(self, "Error locking", str(exc))
            return
        self.close()
        self._on_locked()

    def closeEvent(self, event) -> None:
        if self.db.engine is not None:
            self._session.close()
            self.db.lock()
        event.accept()
