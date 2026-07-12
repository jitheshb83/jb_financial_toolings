from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_app.data.models import (
    Borrowing,
    Debt,
    FixedDeposit,
    Investment,
    NetWorthSnapshot,
    OtherInvestment,
    Transaction,
)
from finance_app.services.currency_service import CurrencyService
from finance_app.services.debt_service import calculate_payoff_plan
from finance_app.services.fd_service import maturity_value
from finance_app.services.investment_service import market_value


class ReportService:
    """Aggregates data across modules into base-currency figures for the
    dashboard. Values that can't be converted (missing exchange rate) are
    skipped and reported separately rather than silently dropped.
    """

    def __init__(self, session: Session, currency_service: CurrencyService):
        self.session = session
        self.currency = currency_service

    def _convert_sum(self, amounts_by_currency: dict[str, float]) -> tuple[float, list[str]]:
        base = self.currency.get_base_currency()
        total = 0.0
        skipped = []
        for currency, amount in amounts_by_currency.items():
            converted = self.currency.try_convert(amount, currency, base)
            if converted is None:
                skipped.append(currency)
            else:
                total += converted
        return total, skipped

    # -- net worth --------------------------------------------------------
    def compute_net_worth(self) -> tuple[float, list[str]]:
        """Net worth = cash position (sum of all transactions) + investments
        + FD principal + other investments + net borrowings (lent - owed,
        pending only) - debt principal (outstanding paydown isn't tracked,
        so this is a conservative estimate using original principal).
        """
        by_currency: dict[str, float] = defaultdict(float)

        for txn in self.session.scalars(select(Transaction)).all():
            by_currency[txn.currency] += txn.amount

        for inv in self.session.scalars(select(Investment)).all():
            by_currency[inv.currency] += market_value(inv)

        for fd in self.session.scalars(select(FixedDeposit)).all():
            by_currency[fd.currency] += fd.principal

        for other in self.session.scalars(select(OtherInvestment)).all():
            by_currency[other.currency] += other.value

        for b in self.session.scalars(select(Borrowing).where(Borrowing.status == "pending")).all():
            by_currency[b.currency] += b.principal if b.direction == "lent" else -b.principal

        for debt in self.session.scalars(select(Debt)).all():
            by_currency[debt.currency] -= debt.principal

        return self._convert_sum(by_currency)

    def record_snapshot_if_needed(self) -> None:
        """Record (or update) today's net worth snapshot."""
        total, _skipped = self.compute_net_worth()
        base = self.currency.get_base_currency()
        today = dt.date.today()
        existing = self.session.scalar(
            select(NetWorthSnapshot).where(NetWorthSnapshot.date == today)
        )
        if existing:
            existing.total_value = total
            existing.base_currency = base
        else:
            self.session.add(NetWorthSnapshot(date=today, total_value=total, base_currency=base))
        self.session.commit()

    def net_worth_history(self) -> list[tuple[dt.date, float]]:
        snapshots = self.session.scalars(select(NetWorthSnapshot).order_by(NetWorthSnapshot.date)).all()
        return [(s.date, s.total_value) for s in snapshots]

    # -- expense breakdown ------------------------------------------------
    def expense_breakdown(
        self, date_from: dt.date | None = None, date_to: dt.date | None = None
    ) -> tuple[dict[str, float], list[str]]:
        """Total spend per category (expenses only, i.e. negative amounts),
        converted to base currency."""
        stmt = select(Transaction).where(Transaction.amount < 0)
        if date_from is not None:
            stmt = stmt.where(Transaction.date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Transaction.date <= date_to)

        by_category_currency: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for txn in self.session.scalars(stmt).all():
            by_category_currency[txn.category][txn.currency] += -txn.amount

        base = self.currency.get_base_currency()
        result: dict[str, float] = {}
        skipped: set[str] = set()
        for category, by_currency in by_category_currency.items():
            total, missing = self._convert_sum(by_currency)
            result[category] = total
            skipped.update(missing)
        return result, sorted(skipped)

    # -- debt payoff timeline -----------------------------------------
    def debt_payoff_timeline(self, extra_monthly_payment: float, method: str):
        debts = self.session.scalars(select(Debt)).all()
        if not debts:
            return None
        return calculate_payoff_plan(debts, extra_monthly_payment, method)

    # -- investment allocation ---------------------------------------
    def investment_allocation(self) -> tuple[dict[str, float], list[str]]:
        """Value by holding type (stock, fund, fixed_deposit, other-investment
        type), converted to base currency."""
        by_type_currency: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for inv in self.session.scalars(select(Investment)).all():
            by_type_currency[inv.type][inv.currency] += market_value(inv)

        for fd in self.session.scalars(select(FixedDeposit)).all():
            by_type_currency["fixed_deposit"][fd.currency] += maturity_value(fd)

        for other in self.session.scalars(select(OtherInvestment)).all():
            by_type_currency[other.type][other.currency] += other.value

        base = self.currency.get_base_currency()
        result: dict[str, float] = {}
        skipped: set[str] = set()
        for type_, by_currency in by_type_currency.items():
            total, missing = self._convert_sum(by_currency)
            if total > 0:
                result[type_] = total
            skipped.update(missing)
        return result, sorted(skipped)
