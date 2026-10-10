from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.enums import ChargeStatus, SourceKind, TotalKind
from app.domain.money import CurrencyMismatchError, Money
from app.domain.products.models import Charge, DataProvenance, PriceBreakdown


def inr(v: str) -> Money:
    return Money(amount=Decimal(v), currency="INR")


class TestMoney:
    def test_float_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Money(amount=0.1, currency="INR")  # type: ignore[arg-type]

    def test_string_and_int_accepted_exactly(self) -> None:
        assert Money(amount="0.10", currency="INR").amount == Decimal("0.10")
        assert Money(amount=5, currency="INR").amount == Decimal(5)

    @pytest.mark.parametrize("bad", ["-1", "NaN", "Infinity"])
    def test_invalid_amounts_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            Money(amount=bad, currency="INR")

    @pytest.mark.parametrize("bad", ["inr", "RS", "INRR", ""])
    def test_invalid_currency_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            Money(amount="1", currency=bad)

    def test_addition_is_exact(self) -> None:
        assert (inr("0.10") + inr("0.20")).amount == Decimal("0.30")

    def test_currency_mismatch_raises(self) -> None:
        with pytest.raises(CurrencyMismatchError):
            inr("1") + Money(amount="1", currency="USD")


class TestCharge:
    def test_known_requires_amount(self) -> None:
        with pytest.raises(ValidationError):
            Charge(name="delivery", status=ChargeStatus.KNOWN)

    def test_unknown_forbids_amount(self) -> None:
        with pytest.raises(ValidationError):
            Charge(name="delivery", status=ChargeStatus.UNKNOWN, amount=inr("0"))

    def test_estimate_requires_known(self) -> None:
        with pytest.raises(ValidationError):
            Charge(name="d", status=ChargeStatus.UNKNOWN, is_estimate=True)


class TestPriceBreakdown:
    def test_known_total(self) -> None:
        p = PriceBreakdown(
            advertised=inr("649"),
            charges=(Charge(name="delivery", status=ChargeStatus.KNOWN, amount=inr("49")),),
            charges_complete=True,
        )
        assert p.total_kind is TotalKind.KNOWN
        assert p.total == inr("698")

    def test_free_delivery_is_known_zero_not_unknown(self) -> None:
        p = PriceBreakdown(
            advertised=inr("689"),
            charges=(Charge(name="delivery", status=ChargeStatus.KNOWN, amount=inr("0")),),
            charges_complete=True,
        )
        assert p.total_kind is TotalKind.KNOWN
        assert p.total == inr("689")

    def test_unknown_charge_makes_total_unknown_not_advertised(self) -> None:
        p = PriceBreakdown(
            advertised=inr("729"),
            charges=(Charge(name="delivery", status=ChargeStatus.UNKNOWN),),
            charges_complete=True,
        )
        assert p.total_kind is TotalKind.UNKNOWN
        assert p.total is None

    def test_incomplete_charge_list_means_unknown_total(self) -> None:
        # Provider did not assert completeness: do not pretend price == total.
        p = PriceBreakdown(advertised=inr("100"))
        assert p.total_kind is TotalKind.UNKNOWN
        assert p.total is None

    def test_estimated_charge_gives_estimated_total(self) -> None:
        p = PriceBreakdown(
            advertised=inr("100"),
            charges=(
                Charge(
                    name="delivery", status=ChargeStatus.KNOWN, amount=inr("40"), is_estimate=True
                ),
            ),
            charges_complete=True,
        )
        assert p.total_kind is TotalKind.ESTIMATED
        assert p.total == inr("140")

    def test_mixed_currency_charge_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PriceBreakdown(
                advertised=inr("100"),
                charges=(
                    Charge(
                        name="fee",
                        status=ChargeStatus.KNOWN,
                        amount=Money(amount="1", currency="USD"),
                    ),
                ),
                charges_complete=True,
            )

    def test_serialized_unknown_total_is_null(self) -> None:
        p = PriceBreakdown(advertised=inr("1"))
        dumped = p.model_dump(mode="json")
        assert dumped["total"] is None
        assert dumped["total_kind"] == "unknown"


class TestProvenance:
    NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)

    def make(self, kind: SourceKind, age_s: int, ttl: int | None = 60) -> DataProvenance:
        return DataProvenance(
            provider_id="p1",
            source_kind=kind,
            retrieved_at=self.NOW - timedelta(seconds=age_s),
            ttl_seconds=ttl,
        )

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DataProvenance(
                provider_id="p1", source_kind=SourceKind.LIVE, retrieved_at=datetime(2026, 1, 1)
            )

    def test_live_becomes_stale_after_ttl(self) -> None:
        assert self.make(SourceKind.LIVE, 30).effective_kind(self.NOW) is SourceKind.LIVE
        assert self.make(SourceKind.LIVE, 61).effective_kind(self.NOW) is SourceKind.STALE

    def test_mock_is_never_reclassified(self) -> None:
        assert self.make(SourceKind.MOCK, 10_000).effective_kind(self.NOW) is SourceKind.MOCK

    def test_confidence_must_be_in_range(self) -> None:
        with pytest.raises(ValidationError):
            DataProvenance(
                provider_id="p1",
                source_kind=SourceKind.LIVE,
                retrieved_at=self.NOW,
                field_confidence={"price": 1.5},
            )
