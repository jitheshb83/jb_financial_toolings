from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_app.data.models import Borrowing

DIRECTIONS = ["lent", "owed"]
STATUSES = ["pending", "settled"]


class BorrowingService:
    def __init__(self, session: Session):
        self.session = session

    def list_borrowings(self, status: str | None = None) -> list[Borrowing]:
        stmt = select(Borrowing).order_by(Borrowing.due_date)
        if status:
            stmt = stmt.where(Borrowing.status == status)
        return self.session.scalars(stmt).all()

    def create_borrowing(
        self,
        counterparty: str,
        direction: str,
        principal: float,
        currency: str,
        due_date: dt.date | None = None,
        status: str = "pending",
    ) -> int:
        if direction not in DIRECTIONS:
            raise ValueError(f"Unknown direction: {direction}")
        borrowing = Borrowing(
            counterparty=counterparty,
            direction=direction,
            principal=principal,
            currency=currency,
            due_date=due_date,
            status=status,
        )
        self.session.add(borrowing)
        self.session.commit()
        return borrowing.id

    def update_borrowing(
        self,
        borrowing_id: int,
        counterparty: str,
        direction: str,
        principal: float,
        currency: str,
        due_date: dt.date | None,
        status: str,
    ) -> None:
        borrowing = self.session.get(Borrowing, borrowing_id)
        if borrowing is None:
            raise KeyError(f"No borrowing with id {borrowing_id}")
        borrowing.counterparty = counterparty
        borrowing.direction = direction
        borrowing.principal = principal
        borrowing.currency = currency
        borrowing.due_date = due_date
        borrowing.status = status
        self.session.commit()

    def mark_settled(self, borrowing_id: int) -> None:
        borrowing = self.session.get(Borrowing, borrowing_id)
        if borrowing is None:
            raise KeyError(f"No borrowing with id {borrowing_id}")
        borrowing.status = "settled"
        self.session.commit()

    def delete_borrowing(self, borrowing_id: int) -> None:
        borrowing = self.session.get(Borrowing, borrowing_id)
        if borrowing is None:
            raise KeyError(f"No borrowing with id {borrowing_id}")
        self.session.delete(borrowing)
        self.session.commit()

    def outstanding_rollup_by_currency(self) -> dict[str, dict[str, float]]:
        """{currency: {"lent": total, "owed": total}} for pending borrowings only."""
        totals: dict[str, dict[str, float]] = defaultdict(lambda: {"lent": 0.0, "owed": 0.0})
        for b in self.list_borrowings(status="pending"):
            totals[b.currency][b.direction] += b.principal
        return dict(totals)
