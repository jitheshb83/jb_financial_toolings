from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_app.data.models import Debt

MAX_SIMULATION_MONTHS = 1200  # 100 years — treated as "won't be paid off"


class DebtService:
    def __init__(self, session: Session):
        self.session = session

    def list_debts(self) -> list[Debt]:
        return self.session.scalars(select(Debt).order_by(Debt.name)).all()

    def create_debt(
        self,
        name: str,
        principal: float,
        interest_rate: float,
        currency: str,
        start_date: dt.date,
        term_months: int,
        minimum_payment: float,
    ) -> int:
        debt = Debt(
            name=name,
            principal=principal,
            interest_rate=interest_rate,
            currency=currency,
            start_date=start_date,
            term_months=term_months,
            minimum_payment=minimum_payment,
        )
        self.session.add(debt)
        self.session.commit()
        return debt.id

    def update_debt(
        self,
        debt_id: int,
        name: str,
        principal: float,
        interest_rate: float,
        currency: str,
        start_date: dt.date,
        term_months: int,
        minimum_payment: float,
    ) -> None:
        debt = self.session.get(Debt, debt_id)
        if debt is None:
            raise KeyError(f"No debt with id {debt_id}")
        debt.name = name
        debt.principal = principal
        debt.interest_rate = interest_rate
        debt.currency = currency
        debt.start_date = start_date
        debt.term_months = term_months
        debt.minimum_payment = minimum_payment
        self.session.commit()

    def delete_debt(self, debt_id: int) -> None:
        debt = self.session.get(Debt, debt_id)
        if debt is None:
            raise KeyError(f"No debt with id {debt_id}")
        self.session.delete(debt)
        self.session.commit()


@dataclass
class DebtPayoffResult:
    debt_id: int
    name: str
    months_to_payoff: int | None  # None if not paid off within MAX_SIMULATION_MONTHS
    payoff_date: dt.date | None
    total_interest_paid: float


@dataclass
class PayoffPlan:
    method: str  # "snowball" | "avalanche"
    per_debt: list[DebtPayoffResult] = field(default_factory=list)
    total_months: int | None = None
    total_payoff_date: dt.date | None = None
    total_interest_paid: float = 0.0
    feasible: bool = True  # False if the budget can't cover accruing interest


def calculate_payoff_plan(
    debts: list[Debt],
    extra_monthly_payment: float,
    method: str,
    start_date: dt.date | None = None,
) -> PayoffPlan:
    """Simulate month-by-month payoff using the snowball (smallest balance
    first) or avalanche (highest interest rate first) method. The combined
    monthly outlay (sum of all minimum payments + extra) stays constant: once
    a debt is paid off, its minimum payment rolls into the extra pool.
    """
    if method not in ("snowball", "avalanche"):
        raise ValueError(f"Unknown method: {method}")
    start_date = start_date or dt.date.today()

    balances = {d.id: d.principal for d in debts}
    rates = {d.id: d.interest_rate for d in debts}
    minimums = {d.id: d.minimum_payment for d in debts}
    names = {d.id: d.name for d in debts}
    total_interest = {d.id: 0.0 for d in debts}
    payoff_month: dict[int, int] = {}

    total_budget = sum(minimums.values()) + extra_monthly_payment

    month = 0
    while any(b > 0.005 for b in balances.values()) and month < MAX_SIMULATION_MONTHS:
        month += 1
        for debt_id, balance in balances.items():
            if balance > 0:
                interest = balance * (rates[debt_id] / 100 / 12)
                balances[debt_id] += interest
                total_interest[debt_id] += interest

        remaining_budget = total_budget
        for debt_id, balance in balances.items():
            if balance > 0:
                pay = min(minimums[debt_id], balance)
                balances[debt_id] -= pay
                remaining_budget -= pay

        active_ids = [d_id for d_id, b in balances.items() if b > 0]
        if method == "snowball":
            active_ids.sort(key=lambda d_id: balances[d_id])
        else:
            active_ids.sort(key=lambda d_id: -rates[d_id])

        for debt_id in active_ids:
            if remaining_budget <= 0:
                break
            extra_pay = min(remaining_budget, balances[debt_id])
            balances[debt_id] -= extra_pay
            remaining_budget -= extra_pay

        for debt_id, balance in balances.items():
            if balance <= 0.005 and debt_id not in payoff_month:
                balances[debt_id] = 0.0
                payoff_month[debt_id] = month

    feasible = all(d.id in payoff_month for d in debts)

    per_debt = []
    for d in debts:
        months = payoff_month.get(d.id)
        payoff_date = start_date + relativedelta(months=months) if months else None
        per_debt.append(
            DebtPayoffResult(
                debt_id=d.id,
                name=names[d.id],
                months_to_payoff=months,
                payoff_date=payoff_date,
                total_interest_paid=total_interest[d.id],
            )
        )

    total_months = max(payoff_month.values()) if feasible and payoff_month else None
    total_payoff_date = start_date + relativedelta(months=total_months) if total_months else None

    return PayoffPlan(
        method=method,
        per_debt=per_debt,
        total_months=total_months,
        total_payoff_date=total_payoff_date,
        total_interest_paid=sum(total_interest.values()),
        feasible=feasible,
    )
