from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_app.data.models import Investment, OtherInvestment


def market_value(investment: Investment) -> float:
    return investment.units * investment.current_price


def gain_loss(investment: Investment) -> float:
    return (investment.current_price - investment.buy_price) * investment.units


class InvestmentService:
    """Stocks/funds and free-form 'other' holdings (gold, real estate, crypto, ...)."""

    def __init__(self, session: Session):
        self.session = session

    # -- stocks / funds --------------------------------------------------
    def list_investments(self) -> list[Investment]:
        return self.session.scalars(select(Investment).order_by(Investment.name)).all()

    def create_investment(
        self,
        name: str,
        type: str,
        currency: str,
        units: float,
        buy_price: float,
        current_price: float,
    ) -> int:
        inv = Investment(
            name=name,
            type=type,
            currency=currency,
            units=units,
            buy_price=buy_price,
            current_price=current_price,
        )
        self.session.add(inv)
        self.session.commit()
        return inv.id

    def update_investment(
        self,
        investment_id: int,
        name: str,
        type: str,
        currency: str,
        units: float,
        buy_price: float,
        current_price: float,
    ) -> None:
        inv = self.session.get(Investment, investment_id)
        if inv is None:
            raise KeyError(f"No investment with id {investment_id}")
        inv.name = name
        inv.type = type
        inv.currency = currency
        inv.units = units
        inv.buy_price = buy_price
        inv.current_price = current_price
        self.session.commit()

    def update_current_price(self, investment_id: int, current_price: float) -> None:
        inv = self.session.get(Investment, investment_id)
        if inv is None:
            raise KeyError(f"No investment with id {investment_id}")
        inv.current_price = current_price
        self.session.commit()

    def delete_investment(self, investment_id: int) -> None:
        inv = self.session.get(Investment, investment_id)
        if inv is None:
            raise KeyError(f"No investment with id {investment_id}")
        self.session.delete(inv)
        self.session.commit()

    # -- other investments -------------------------------------------------
    def list_other_investments(self) -> list[OtherInvestment]:
        return self.session.scalars(select(OtherInvestment).order_by(OtherInvestment.name)).all()

    def create_other_investment(
        self, name: str, type: str, currency: str, value: float, note: str | None = None
    ) -> int:
        other = OtherInvestment(name=name, type=type, currency=currency, value=value, note=note or None)
        self.session.add(other)
        self.session.commit()
        return other.id

    def update_other_investment(
        self,
        other_id: int,
        name: str,
        type: str,
        currency: str,
        value: float,
        note: str | None = None,
    ) -> None:
        other = self.session.get(OtherInvestment, other_id)
        if other is None:
            raise KeyError(f"No other investment with id {other_id}")
        other.name = name
        other.type = type
        other.currency = currency
        other.value = value
        other.note = note or None
        self.session.commit()

    def delete_other_investment(self, other_id: int) -> None:
        other = self.session.get(OtherInvestment, other_id)
        if other is None:
            raise KeyError(f"No other investment with id {other_id}")
        self.session.delete(other)
        self.session.commit()

    # -- rollups -------------------------------------------------------
    def rollup_by_currency(self) -> dict[str, float]:
        """Sum of stocks/funds market value + other investments, per currency."""
        totals: dict[str, float] = defaultdict(float)
        for inv in self.list_investments():
            totals[inv.currency] += market_value(inv)
        for other in self.list_other_investments():
            totals[other.currency] += other.value
        return dict(totals)
