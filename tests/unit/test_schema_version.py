from casino_intel.sheets.schema import ensure_tabs_and_headers
from casino_intel.sheets.schema_version import (
    CURRENT_SCHEMA_VERSION,
    get_recorded_schema_version,
    is_up_to_date,
    record_migration,
)


def test_get_recorded_schema_version_none_on_fresh_workbook(sheets_client):
    ensure_tabs_and_headers(sheets_client)
    assert get_recorded_schema_version(sheets_client) is None
    assert is_up_to_date(sheets_client)  # nothing recorded yet == not stale


def test_get_recorded_schema_version_reads_readme_row(sheets_client, fake_service):
    ensure_tabs_and_headers(sheets_client)
    fake_service.sheets["README"].append(["0.1.0", CURRENT_SCHEMA_VERSION, "", "", "", "", "", ""])
    assert get_recorded_schema_version(sheets_client) == CURRENT_SCHEMA_VERSION
    assert is_up_to_date(sheets_client)


def test_is_up_to_date_false_for_stale_workbook(sheets_client, fake_service):
    ensure_tabs_and_headers(sheets_client)
    fake_service.sheets["README"].append(["0.1.0", "0.0.1", "", "", "", "", "", ""])
    assert not is_up_to_date(sheets_client)


def test_record_migration_appends_without_overwriting(tmp_path):
    log_path = tmp_path / "migrations.md"
    record_migration("0.1.0", "0.2.0", "Added a column.", path=log_path)
    record_migration("0.2.0", "0.3.0", "Added another column.", path=log_path)

    content = log_path.read_text()
    assert "0.1.0 -> 0.2.0" in content
    assert "0.2.0 -> 0.3.0" in content
    assert "Added a column." in content
    assert "Added another column." in content
