from __future__ import annotations

import datetime as dt

from sqlalchemy import ForeignKey, LargeBinary
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    type: Mapped[str]  # bank / cash / broker
    currency: Mapped[str] = mapped_column(default="USD")

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    date: Mapped[dt.date]
    category: Mapped[str]
    amount: Mapped[float]
    currency: Mapped[str]
    is_recurring: Mapped[bool] = mapped_column(default=False)
    recurrence_rule: Mapped[str | None] = mapped_column(default=None)
    note: Mapped[str | None] = mapped_column(default=None)

    account: Mapped["Account"] = relationship(back_populates="transactions")


class Debt(Base):
    __tablename__ = "debts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    principal: Mapped[float]
    interest_rate: Mapped[float]
    currency: Mapped[str]
    start_date: Mapped[dt.date]
    term_months: Mapped[int]
    minimum_payment: Mapped[float]


class Investment(Base):
    __tablename__ = "investments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    type: Mapped[str]  # stock / fund
    currency: Mapped[str]
    units: Mapped[float]
    buy_price: Mapped[float]
    current_price: Mapped[float]


class FixedDeposit(Base):
    __tablename__ = "fixed_deposits"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    principal: Mapped[float]
    interest_rate: Mapped[float]
    currency: Mapped[str]
    start_date: Mapped[dt.date]
    maturity_date: Mapped[dt.date]


class OtherInvestment(Base):
    __tablename__ = "other_investments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    type: Mapped[str]
    currency: Mapped[str]
    value: Mapped[float]
    note: Mapped[str | None] = mapped_column(default=None)


class Borrowing(Base):
    __tablename__ = "borrowings"

    id: Mapped[int] = mapped_column(primary_key=True)
    counterparty: Mapped[str]
    direction: Mapped[str]  # lent / owed
    principal: Mapped[float]
    currency: Mapped[str]
    due_date: Mapped[dt.date | None]
    status: Mapped[str] = mapped_column(default="pending")  # pending / settled


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    currency_pair: Mapped[str]  # e.g. "USD_EUR" meaning 1 USD = rate EUR
    rate: Mapped[float]
    date: Mapped[dt.date]


class AppSetting(Base):
    """Generic key/value store for small app settings (base currency, theme, ...)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]


class NetWorthSnapshot(Base):
    """One recorded net-worth data point (see report_service.record_snapshot_if_needed).

    `base_currency` records what the value was computed in so history isn't
    silently reinterpreted if the user later switches base currency.
    """

    __tablename__ = "net_worth_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date]
    total_value: Mapped[float]
    base_currency: Mapped[str]


class VaultItem(Base):
    """A password-vault entry. `payload_ciphertext` and `payload_nonce` hold
    the AES-256-GCM-encrypted, type-specific fields (see security/vault_crypto.py).
    Metadata below stays as normal fields so the app can list/search without
    decrypting every payload up front.
    """

    __tablename__ = "vault_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str]  # login / secure_note / card / identity
    title: Mapped[str]
    folder: Mapped[str | None] = mapped_column(default=None)
    tags: Mapped[str | None] = mapped_column(default=None)
    payload_nonce: Mapped[bytes] = mapped_column(LargeBinary)
    payload_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[dt.datetime]
    updated_at: Mapped[dt.datetime]
