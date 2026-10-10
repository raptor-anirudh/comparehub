"""Money value object. Decimal only; floats are rejected on purpose."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CurrencyMismatchError(ValueError):
    """Raised when combining Money values of different currencies."""


class Money(BaseModel):
    """A non-negative monetary amount with an ISO-4217-style currency code."""

    model_config = ConfigDict(frozen=True)

    amount: Decimal = Field(ge=0, allow_inf_nan=False)
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @field_validator("amount", mode="before")
    @classmethod
    def _reject_float(cls, value: Any) -> Any:
        # Binary floats cannot represent most decimal prices exactly.
        if isinstance(value, float):
            raise ValueError("amount must be a Decimal, int, or numeric string, not float")
        return value

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"cannot add {self.currency} and {other.currency}")
        return Money(amount=self.amount + other.amount, currency=self.currency)
