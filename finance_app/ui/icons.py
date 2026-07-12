"""Central place to name icons used across the app (qtawesome Font Awesome set)."""
from __future__ import annotations

import qtawesome as qta

_NAMES = {
    "dashboard": "fa5s.chart-line",
    "expenses": "fa5s.receipt",
    "debts": "fa5s.credit-card",
    "investments": "fa5s.chart-pie",
    "borrowings": "fa5s.handshake",
    "currency": "fa5s.dollar-sign",
    "vault": "fa5s.lock",
    "add": "fa5s.plus",
    "edit": "fa5s.edit",
    "delete": "fa5s.trash-alt",
    "copy": "fa5s.copy",
    "settle": "fa5s.check-circle",
    "refresh": "fa5s.sync-alt",
    "lock": "fa5s.lock",
    "browse": "fa5s.folder-open",
    "calculate": "fa5s.calculator",
}


def icon(name: str) -> qta.icon:
    return qta.icon(_NAMES[name])
