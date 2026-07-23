from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from finance_app.data.database import DatabaseManager
from finance_app.security.crypto import WrongPassword
from finance_app.ui.dialogs.unlock_dialog import UnlockDialog
from finance_app.ui.main_window import MainWindow

RESOURCES_DIR = Path(__file__).parent / "resources"


class AppController:
    def __init__(self, app: QApplication):
        self.app = app
        self.window: MainWindow | None = None

    def start(self) -> None:
        self._show_unlock_dialog()

    def _show_unlock_dialog(self) -> None:
        dialog = UnlockDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.app.quit()
            return

        db = DatabaseManager(dialog.file_path)
        try:
            db.unlock(dialog.password)
        except WrongPassword:
            QMessageBox.critical(None, "Unlock failed", "Incorrect master password.")
            self._show_unlock_dialog()
            return
        except Exception as exc:  # pragma: no cover - defensive UI feedback
            QMessageBox.critical(None, "Error", f"Could not open data file:\n{exc}")
            self._show_unlock_dialog()
            return

        self.window = MainWindow(db, on_locked=self._show_unlock_dialog)
        self.window.show()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Personal Finance")
    app.setWindowIcon(QIcon(str(RESOURCES_DIR / "logo_icon.png")))
    controller = AppController(app)
    controller.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
