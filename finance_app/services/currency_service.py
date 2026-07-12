from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_app.data.models import AppSetting, ExchangeRate

BASE_CURRENCY_KEY = "base_currency"
DEFAULT_BASE_CURRENCY = "USD"


class RateNotFound(Exception):
    """Raised when no exchange rate (direct or inverse) exists for a currency pair."""


class CurrencyService:
    """Base currency setting + a manually maintained exchange rate table.

    Rates are stored as currency_pair "FROM_TO" meaning 1 FROM = rate TO.
    Conversion looks up the most recent rate for the pair, falling back to
    the inverse of the reverse pair if that's what was entered.
    """

    def __init__(self, session: Session):
        self.session = session

    # -- base currency ---------------------------------------------------
    def get_base_currency(self) -> str:
        setting = self.session.get(AppSetting, BASE_CURRENCY_KEY)
        return setting.value if setting else DEFAULT_BASE_CURRENCY

    def set_base_currency(self, code: str) -> None:
        code = code.strip().upper()
        setting = self.session.get(AppSetting, BASE_CURRENCY_KEY)
        if setting is None:
            setting = AppSetting(key=BASE_CURRENCY_KEY, value=code)
            self.session.add(setting)
        else:
            setting.value = code
        self.session.commit()

    # -- rate table -----------------------------------------------------
    def list_rates(self) -> list[ExchangeRate]:
        return self.session.scalars(
            select(ExchangeRate).order_by(ExchangeRate.currency_pair, ExchangeRate.date.desc())
        ).all()

    def set_rate(self, from_currency: str, to_currency: str, rate: float, date: dt.date) -> int:
        pair = f"{from_currency.strip().upper()}_{to_currency.strip().upper()}"
        entry = ExchangeRate(currency_pair=pair, rate=rate, date=date)
        self.session.add(entry)
        self.session.commit()
        return entry.id

    def delete_rate(self, rate_id: int) -> None:
        entry = self.session.get(ExchangeRate, rate_id)
        if entry is None:
            raise KeyError(f"No exchange rate with id {rate_id}")
        self.session.delete(entry)
        self.session.commit()

    def _latest_rate_for_pair(self, pair: str) -> float | None:
        stmt = (
            select(ExchangeRate)
            .where(ExchangeRate.currency_pair == pair)
            .order_by(ExchangeRate.date.desc(), ExchangeRate.id.desc())
        )
        entry = self.session.scalars(stmt).first()
        return entry.rate if entry else None

    # -- conversion -----------------------------------------------------
    def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        from_currency, to_currency = from_currency.upper(), to_currency.upper()
        if from_currency == to_currency:
            return amount

        direct = self._latest_rate_for_pair(f"{from_currency}_{to_currency}")
        if direct is not None:
            return amount * direct

        inverse = self._latest_rate_for_pair(f"{to_currency}_{from_currency}")
        if inverse:
            return amount / inverse

        raise RateNotFound(f"No exchange rate found for {from_currency} -> {to_currency}")

    def try_convert(self, amount: float, from_currency: str, to_currency: str) -> float | None:
        try:
            return self.convert(amount, from_currency, to_currency)
        except RateNotFound:
            return None
