import pytest

from casino_intel.services.registry_service import RegistryService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS


@pytest.fixture(autouse=True)
def _sheets(fake_service):
    fake_service.add_sheet("Operators", SHEET_HEADERS["Operators"])
    fake_service.add_sheet("Brands", SHEET_HEADERS["Brands"])
    fake_service.add_sheet("Licences", SHEET_HEADERS["Licences"])


@pytest.fixture
def registry_service(sheets_writer):
    return RegistryService(sheets_writer)


def test_register_operator_appends_row(registry_service, fake_service):
    result = registry_service.register_operator(
        {"operator_name": "Example Group plc", "ownership_type": "public"}, actor="tester"
    )
    assert result.written
    header = SHEET_HEADERS["Operators"]
    row = dict(zip(header, fake_service.sheets["Operators"][1], strict=False))
    assert row["operator_name"] == "Example Group plc"
    assert row["ownership_type"] == "public"


def test_register_brand_links_to_operator(registry_service, fake_service):
    operator = registry_service.register_operator(
        {"operator_name": "Example Group"}, actor="tester"
    )
    brand = registry_service.register_brand(
        {
            "brand_name": "Example Casino",
            "operator_id": operator.record_id,
            "primary_domain": "example-casino.example",
            "brand_type": "casino_only",
            "sampling_rationale": "Test brand for unit coverage.",
        },
        actor="tester",
    )
    header = SHEET_HEADERS["Brands"]
    row = dict(zip(header, fake_service.sheets["Brands"][1], strict=False))
    assert row["operator_id"] == operator.record_id
    assert brand.written


def test_bulk_load_registers_operators_before_brands(registry_service, fake_service):
    results = registry_service.bulk_load(
        operators=[{"operator_name": "Group A"}],
        brands=[
            {
                "brand_name": "Brand A",
                "operator_id": "placeholder",
                "primary_domain": "brand-a.example",
                "brand_type": "casino_only",
            }
        ],
        actor="tester",
    )
    assert len(results["operators"]) == 1
    assert len(results["brands"]) == 1
    assert len(fake_service.sheets["Operators"]) == 2
    assert len(fake_service.sheets["Brands"]) == 2
