"""Currency/FX normalisation (spec FR-005, source doc §3.3).

Always retains the original value+currency alongside the normalised value,
the exact rate used, the date of that rate, and the calculation method —
never discards the raw figure (design principle §3.3).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

FxRateProvider = Callable[[str, str, str], float]

#: Placeholder static rates (documented as such) — replace with a real FX
#: data source before relying on this for anything beyond development/testing.
_STATIC_RATES: dict[tuple[str, str], float] = {
    ("EUR", "GBP"): 0.86,
    ("USD", "GBP"): 0.79,
    ("CAD", "GBP"): 0.58,
    ("SEK", "GBP"): 0.075,
    ("DKK", "GBP"): 0.115,
}


def static_fx_rate_provider(from_currency: str, to_currency: str, as_of_date: str) -> float:
    """Development/test-only FX provider using fixed placeholder rates.

    Raises `KeyError` for unsupported pairs rather than guessing — an
    unsupported currency must surface as a `unsupported_currency` Data
    Quality issue (FR-020), not a fabricated conversion.
    """
    if from_currency == to_currency:
        return 1.0
    return _STATIC_RATES[(from_currency, to_currency)]


@dataclass(frozen=True)
class NormalisedCurrencyValue:
    raw_value: float
    raw_currency: str
    normalised_value: float
    normalised_currency: str
    fx_rate: float
    fx_rate_date: str
    calculation_method: str


def normalise_currency(
    raw_value: float,
    raw_currency: str,
    target_currency: str = "GBP",
    as_of_date: str = "",
    provider: FxRateProvider = static_fx_rate_provider,
) -> NormalisedCurrencyValue:
    """Convert `raw_value` in `raw_currency` to `target_currency`, retaining
    every input alongside the result (spec FR-005)."""
    rate = provider(raw_currency, target_currency, as_of_date)
    return NormalisedCurrencyValue(
        raw_value=raw_value,
        raw_currency=raw_currency,
        normalised_value=round(raw_value * rate, 2),
        normalised_currency=target_currency,
        fx_rate=rate,
        fx_rate_date=as_of_date,
        calculation_method=(
            f"static_placeholder_rate: {raw_currency}->{target_currency}"
            if provider is static_fx_rate_provider
            else "external_fx_rate_provider"
        ),
    )
