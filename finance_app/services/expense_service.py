from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_app.data.models import Account, Transaction

DEFAULT_CATEGORIES = [
    "Groceries",
    "Rent/Mortgage",
    "Utilities",
    "Transport",
    "Dining",
    "Entertainment",
    "Health",
    "Shopping",
    "Travel",
    "Income",
    "Other",
]


class ExpenseService:
    """Account + transaction management for the expense-tracking module."""

    def __init__(self, session: Session):
        self.session = session

    # -- accounts -----------------------------------------------------
    def list_accounts(self) -> list[Account]:
        return self.session.scalars(select(Account).order_by(Account.name)).all()

    def create_account(self, name: str, type: str, currency: str) -> int:
        account = Account(name=name, type=type, currency=currency)
        self.session.add(account)
        self.session.commit()
        return account.id

    # -- transactions ---------------------------------------------------
    def list_transactions(
        self,
        account_id: int | None = None,
        category: str | None = None,
        currency: str | None = None,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
    ) -> list[Transaction]:
        stmt = select(Transaction).order_by(Transaction.date.desc(), Transaction.id.desc())
        if account_id is not None:
            stmt = stmt.where(Transaction.account_id == account_id)
        if category:
            stmt = stmt.where(Transaction.category == category)
        if currency:
            stmt = stmt.where(Transaction.currency == currency)
        if date_from is not None:
            stmt = stmt.where(Transaction.date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Transaction.date <= date_to)
        return self.session.scalars(stmt).all()

    def list_categories(self) -> list[str]:
        used = self.session.scalars(select(Transaction.category).distinct()).all()
        return sorted(set(DEFAULT_CATEGORIES) | set(used))

    def create_transaction(
        self,
        account_id: int,
        date: dt.date,
        category: str,
        amount: float,
        currency: str,
        is_recurring: bool = False,
        recurrence_rule: str | None = None,
        note: str | None = None,
    ) -> int:
        txn = Transaction(
            account_id=account_id,
            date=date,
            category=category,
            amount=amount,
            currency=currency,
            is_recurring=is_recurring,
            recurrence_rule=recurrence_rule if is_recurring else None,
            note=note or None,
        )
        self.session.add(txn)
        self.session.commit()
        return txn.id

    def update_transaction(
        self,
        txn_id: int,
        account_id: int,
        date: dt.date,
        category: str,
        amount: float,
        currency: str,
        is_recurring: bool = False,
        recurrence_rule: str | None = None,
        note: str | None = None,
    ) -> None:
        txn = self.session.get(Transaction, txn_id)
        if txn is None:
            raise KeyError(f"No transaction with id {txn_id}")
        txn.account_id = account_id
        txn.date = date
        txn.category = category
        txn.amount = amount
        txn.currency = currency
        txn.is_recurring = is_recurring
        txn.recurrence_rule = recurrence_rule if is_recurring else None
        txn.note = note or None
        self.session.commit()

    def delete_transaction(self, txn_id: int) -> None:
        txn = self.session.get(Transaction, txn_id)
        if txn is None:
            raise KeyError(f"No transaction with id {txn_id}")
        self.session.delete(txn)
        self.session.commit()
