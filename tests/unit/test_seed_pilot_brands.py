import sys
from pathlib import Path

import pytest

from casino_intel.cli.context import AppContext
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import seed_pilot_brands  # noqa: E402


@pytest.fixture(autouse=True)
def _sheets(fake_service):
    fake_service.add_sheet("Operators", SHEET_HEADERS["Operators"])
    fake_service.add_sheet("Brands", SHEET_HEADERS["Brands"])


def test_load_seed_parses_yaml():
    seed = seed_pilot_brands.load_seed()
    assert 10 <= len(seed["operators"]) <= 20
    assert 15 <= len(seed["brands"]) <= 20


def test_seed_includes_stratified_pilot_criteria():
    """spec §14: pilot must include a crypto-native comparator clearly
    separated from GB-licensed brands, plus scale/proposition variety."""
    seed = seed_pilot_brands.load_seed()
    brand_types = {b["brand_type"] for b in seed["brands"]}
    assert "crypto" in brand_types
    assert "casino_only" in brand_types
    assert "hybrid" in brand_types

    crypto_brand = next(b for b in seed["brands"] if b["brand_type"] == "crypto")
    assert "GB" in crypto_brand.get("restricted_markets", [])

    assert all(b.get("sampling_rationale") for b in seed["brands"])


def test_run_resolves_operator_alias_to_generated_operator_id(sheets_writer, fake_service):
    context = AppContext(dry_run=False, _writer=sheets_writer)
    seed = seed_pilot_brands.load_seed()

    results = seed_pilot_brands.run(context, seed)

    assert len(results["operators"]) == len(seed["operators"])
    assert len(results["brands"]) == len(seed["brands"])

    header = SHEET_HEADERS["Brands"]
    operator_id_col = header.index("operator_id")
    operator_ids_seen = {row[operator_id_col] for row in fake_service.sheets["Brands"][1:]}
    assert operator_ids_seen == set(results["operators"])  # every brand links to a real operator
