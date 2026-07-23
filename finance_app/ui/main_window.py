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
from finance_app.settings import AppSettings
from finance_app.sync.drive_auth import DriveAuthManager
from finance_app.sync.drive_sync_service import DriveConflictError, DriveSyncService
from finance_app.ui.icons import icon
from finance_app.ui.views.borrowings_view import BorrowingsView
from finance_app.ui.views.currency_view import CurrencyView
from finance_app.ui.views.dashboard_view import DashboardView
from finance_app.ui.views.debt_view import DebtView
from finance_app.ui.views.expenses_view import ExpensesView
from finance_app.ui.views.investments_view import InvestmentsView
from finance_app.ui.views.vault_view import VaultView

IDLE_LOCK_SECONDS = 5 * 60
DRIVE_SYNC_RETRY_SECONDS = 5 * 60


class MainWindow(QMainWindow):
    def __init__(
        self,
        db: DatabaseManager,
        on_locked,
        sync_service: DriveSyncService | None = None,
        settings: AppSettings | None = None,
        auth_manager: DriveAuthManager | None = None,
    ):
        super().__init__()
        self.db = db
        self._on_locked = on_locked
        self._session = db.session()
        self.sync_service = sync_service
        self.settings = settings or AppSettings()
        self.auth_manager = auth_manager or DriveAuthManager()
        self._sync_dirty = False

        self.setWindowTitle("Personal Finance")
        self.resize(1000, 700)

        self._idle_timer = QTimer(self)
        self._idle_timer.setInterval(IDLE_LOCK_SECONDS * 1000)
        self._idle_timer.timeout.connect(self.lock)
        self._idle_timer.start()

        # Retries a push periodically, but only if one is actually pending
        # (e.g. the last attempt failed due to a network blip) — not an
        # unconditional re-upload on a fixed schedule, which would just waste
        # bandwidth re-sending unchanged bytes.
        self._drive_retry_timer = QTimer(self)
        self._drive_retry_timer.setInterval(DRIVE_SYNC_RETRY_SECONDS * 1000)
        self._drive_retry_timer.timeout.connect(self._retry_pending_sync)
        self._drive_retry_timer.start()

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

        file_menu = self.menuBar().addMenu("&File")
        lock_action = file_menu.addAction(icon("lock"), "Lock now")
        lock_action.triggered.connect(self.lock)

        file_menu.addSeparator()
        self.sync_now_action = file_menu.addAction(icon("refresh"), "Sync now")
        self.sync_now_action.setEnabled(self.sync_service is not None)
        self.sync_now_action.triggered.connect(self._sync_now)

        self.sync_toggle_action = file_menu.addAction("Sync with Google Drive")
        self.sync_toggle_action.setCheckable(True)
        self.sync_toggle_action.setChecked(self.settings.is_drive_sync_enabled())
        self.sync_toggle_action.toggled.connect(self._on_sync_toggle)

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
        self._auto_sync_push()

    def _auto_sync_push(self) -> None:
        if self.sync_service is None or not self.settings.is_drive_sync_enabled():
            return
        self._sync_dirty = True
        try:
            self.sync_service.push()
            self._sync_dirty = False
        except DriveConflictError as exc:
            QMessageBox.warning(self, "Sync conflict", str(exc))
        except Exception as exc:  # pragma: no cover - never block local saves on connectivity
            self.statusBar().showMessage(f"Drive sync failed — will retry ({exc})", 5000)

    def _retry_pending_sync(self) -> None:
        if self._sync_dirty:
            self._auto_sync_push()

    def _sync_now(self) -> None:
        if self.sync_service is None:
            return
        try:
            self.sync_service.push()
            self._sync_dirty = False
            self.statusBar().showMessage("Synced with Google Drive.", 3000)
        except DriveConflictError as exc:
            QMessageBox.warning(self, "Sync conflict", str(exc))
        except Exception as exc:
            self._sync_dirty = True
            QMessageBox.warning(self, "Sync failed", str(exc))

    def _on_sync_toggle(self, checked: bool) -> None:
        if checked and self.sync_service is None:
            try:
                new_service = DriveSyncService(self.auth_manager, self.db.encrypted_path)
                new_file_id = new_service.link_new_file()
            except Exception as exc:
                QMessageBox.warning(self, "Could not link to Drive", str(exc))
                self.sync_toggle_action.blockSignals(True)
                self.sync_toggle_action.setChecked(False)
                self.sync_toggle_action.blockSignals(False)
                return
            self.sync_service = new_service
            self.settings.set_last_file(str(self.db.encrypted_path), new_file_id)
            self.sync_now_action.setEnabled(True)
        self.settings.set_drive_sync_enabled(checked)

    def lock(self) -> None:
        self._idle_timer.stop()
        self._drive_retry_timer.stop()
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
