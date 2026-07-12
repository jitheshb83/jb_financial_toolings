from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication

DEFAULT_CLEAR_SECONDS = 25


def copy_with_autoclear(text: str, seconds: int = DEFAULT_CLEAR_SECONDS) -> None:
    """Copy text to the clipboard and clear it again after `seconds`,
    but only if the clipboard still holds exactly what we put there
    (so we don't wipe something the user copied in the meantime).
    """
    clipboard: QClipboard = QApplication.clipboard()
    clipboard.setText(text)

    def _maybe_clear() -> None:
        if clipboard.text() == text:
            clipboard.clear()

    QTimer.singleShot(seconds * 1000, _maybe_clear)
