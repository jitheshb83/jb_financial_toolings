from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

INVESTMENT_TYPES = ["stock", "fund"]


class InvestmentDialog(QDialog):
    def __init__(
        self,
        parent=None,
        name: str = "",
        type: str = "stock",
        currency: str = "USD",
        units: float = 0.0,
        buy_price: float = 0.0,
        current_price: float = 0.0,
    ):
        super().__init__(parent)
        self.setWindowTitle("Investment")
        self.setMinimumWidth(340)

        self.name_edit = QLineEdit(name)

        self.type_combo = QComboBox()
        self.type_combo.addItems(INVESTMENT_TYPES)
        self.type_combo.setCurrentText(type)

        self.currency_edit = QLineEdit(currency)

        self.units_spin = QDoubleSpinBox()
        self.units_spin.setRange(0, 1_000_000_000)
        self.units_spin.setDecimals(4)
        self.units_spin.setValue(units)

        self.buy_price_spin = QDoubleSpinBox()
        self.buy_price_spin.setRange(0, 1_000_000_000)
        self.buy_price_spin.setDecimals(4)
        self.buy_price_spin.setValue(buy_price)

        self.current_price_spin = QDoubleSpinBox()
        self.current_price_spin.setRange(0, 1_000_000_000)
        self.current_price_spin.setDecimals(4)
        self.current_price_spin.setValue(current_price or buy_price)

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        form.addRow("Type", self.type_combo)
        form.addRow("Currency", self.currency_edit)
        form.addRow("Units", self.units_spin)
        form.addRow("Buy price", self.buy_price_spin)
        form.addRow("Current price", self.current_price_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @property
    def name(self) -> str:
        return self.name_edit.text().strip()

    @property
    def type(self) -> str:
        return self.type_combo.currentText()

    @property
    def currency(self) -> str:
        return self.currency_edit.text().strip().upper()

    @property
    def units(self) -> float:
        return self.units_spin.value()

    @property
    def buy_price(self) -> float:
        return self.buy_price_spin.value()

    @property
    def current_price(self) -> float:
        return self.current_price_spin.value()
