from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_app.data.models import FixedDeposit


def maturity_value(fd: FixedDeposit) -> float:
    """Simple-interest estimate of the payout at maturity."""
    years = (fd.maturity_date - fd.start_date).days / 365.25
    return fd.principal * (1 + fd.interest_rate / 100 * years)


class FDService:
    def __init__(self, session: Session):
        self.session = session

    def list_fds(self) -> list[FixedDeposit]:
        return self.session.scalars(select(FixedDeposit).order_by(FixedDeposit.maturity_date)).all()

    def create_fd(
        self,
        name: str,
        principal: float,
        interest_rate: float,
        currency: str,
        start_date: dt.date,
        maturity_date: dt.date,
    ) -> int:
        fd = FixedDeposit(
            name=name,
            principal=principal,
            interest_rate=interest_rate,
            currency=currency,
            start_date=start_date,
            maturity_date=maturity_date,
        )
        self.session.add(fd)
        self.session.commit()
        return fd.id

    def update_fd(
        self,
        fd_id: int,
        name: str,
        principal: float,
        interest_rate: float,
        currency: str,
        start_date: dt.date,
        maturity_date: dt.date,
    ) -> None:
        fd = self.session.get(FixedDeposit, fd_id)
        if fd is None:
            raise KeyError(f"No fixed deposit with id {fd_id}")
        fd.name = name
        fd.principal = principal
        fd.interest_rate = interest_rate
        fd.currency = currency
        fd.start_date = start_date
        fd.maturity_date = maturity_date
        self.session.commit()

    def delete_fd(self, fd_id: int) -> None:
        fd = self.session.get(FixedDeposit, fd_id)
        if fd is None:
            raise KeyError(f"No fixed deposit with id {fd_id}")
        self.session.delete(fd)
        self.session.commit()

    def rollup_by_currency(self) -> dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        for fd in self.list_fds():
            totals[fd.currency] += fd.principal
        return dict(totals)
