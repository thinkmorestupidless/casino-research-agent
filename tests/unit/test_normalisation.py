import pytest

from casino_intel.normalisation.currency import normalise_currency
from casino_intel.normalisation.units import (
    parse_boolean,
    parse_date,
    parse_number,
    parse_percentage,
)


def test_normalise_currency_retains_raw_and_computes_gbp():
    result = normalise_currency(450_000_000, "EUR", "GBP", as_of_date="2026-06-30")
    assert result.raw_value == 450_000_000
    assert result.raw_currency == "EUR"
    assert result.normalised_currency == "GBP"
    assert result.fx_rate == 0.86
    assert result.fx_rate_date == "2026-06-30"
    assert result.normalised_value == pytest.approx(450_000_000 * 0.86, rel=1e-6)
    assert result.calculation_method


def test_normalise_currency_same_currency_is_identity():
    result = normalise_currency(100.0, "GBP", "GBP", as_of_date="2026-06-30")
    assert result.fx_rate == 1.0
    assert result.normalised_value == 100.0


def test_normalise_currency_unsupported_pair_raises():
    with pytest.raises(KeyError):
        normalise_currency(100.0, "JPY", "GBP", as_of_date="2026-06-30")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1,200,000", 1_200_000),
        ("4.2 million", 4_200_000),
        ("3.5k", 3_500),
        ("1.1bn", 1_100_000_000),
        ("42", 42),
    ],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == pytest.approx(expected)


def test_parse_percentage_valid():
    assert parse_percentage("42.5%") == pytest.approx(42.5)


def test_parse_percentage_out_of_range_raises():
    with pytest.raises(ValueError):
        parse_percentage("142%")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-06-30", "2026-06-30"),
        ("30/06/2026", "2026-06-30"),
        ("30 June 2026", "2026-06-30"),
        ("June 2026", "2026-06-01"),
        ("2026", "2026-01-01"),
    ],
)
def test_parse_date(raw, expected):
    assert parse_date(raw).isoformat() == expected


def test_parse_date_unrecognised_raises():
    with pytest.raises(ValueError):
        parse_date("not a date")


@pytest.mark.parametrize("raw,expected", [("true", True), ("No", False), ("1", True), ("0", False)])
def test_parse_boolean(raw, expected):
    assert parse_boolean(raw) is expected


def test_parse_boolean_unrecognised_raises():
    with pytest.raises(ValueError):
        parse_boolean("maybe")
