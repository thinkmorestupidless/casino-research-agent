import pytest

from casino_intel.sheets.safety import escape_cell_value, escape_row


@pytest.mark.parametrize("dangerous", ["=SUM(A1:A9)", "+1+1", "-1", "@import"])
def test_escape_cell_value_neutralises_leading_formula_chars(dangerous):
    escaped = escape_cell_value(dangerous)
    assert escaped.startswith("'")
    assert escaped == f"'{dangerous}"


@pytest.mark.parametrize("safe", ["hello", "100% welcome bonus", "", "GBP"])
def test_escape_cell_value_leaves_safe_strings_untouched(safe):
    assert escape_cell_value(safe) == safe


def test_escape_cell_value_passes_through_non_strings():
    assert escape_cell_value(42) == 42
    assert escape_cell_value(None) is None
    assert escape_cell_value(True) is True


def test_escape_row_applies_to_every_cell():
    row = ["=1+1", "safe", "-negative", 7]
    assert escape_row(row) == ["'=1+1", "safe", "'-negative", 7]
