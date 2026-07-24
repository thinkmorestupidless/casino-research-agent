"""Full quickstart.md walkthrough (T101), executed against the in-memory
Sheets/Drive test harness rather than a live Google Cloud spreadsheet —
this sandbox has no real Google Cloud credentials available (see
docs/runbook.md's "Quickstart validation record" section for the honest
status of live validation). This test exercises the exact same CLI command
sequence a real operator would run, proving every subsystem (Sheets/Drive
clients, ingestion pipeline, review workflow, derivation engine, summary
generator, export, research queue) wires together correctly end-to-end.

Covers quickstart.md Steps 1-3, 5-7, 9-11 (Step 4's second/third format and
Step 8's audit capture are exercised in their own User Story test files —
`test_user_story_2.py`, `test_user_story_3.py` — and not repeated here).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from casino_intel.cli.app import app
from casino_intel.drive.client import DriveClient
from casino_intel.sheets.schema_definitions import SHEET_HEADERS, TAB_NAMES

runner = CliRunner()
FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "ukgc_business_data.xlsx"


class _FakeDriveService:
    """Minimal in-memory Drive API v3 stand-in (mirrors test_user_story_2.py's)."""

    def __init__(self) -> None:
        self._next_id = 1
        self._pending: tuple[Any, ...] = ()

    def files(self) -> _FakeDriveService:
        return self

    def list(self, q: str, fields: str, **kwargs: object) -> _FakeDriveService:
        self._pending = ("list",)
        return self

    def create(
        self,
        body: dict,
        fields: str = "id",
        media_body: object | None = None,
        **kwargs: object,
    ) -> _FakeDriveService:
        self._pending = ("create",)
        return self

    def execute(self) -> dict:
        if self._pending[0] == "list":
            return {"files": []}
        new_id = f"fake-drive-file-{self._next_id}"
        self._next_id += 1
        return {"id": new_id}


@pytest.fixture(autouse=True)
def _setup(monkeypatch, sheets_client, fake_service):
    monkeypatch.setenv("SPREADSHEET_ID", "fake-spreadsheet")
    monkeypatch.setenv("CASINO_INTEL_CACHE_PATH", ":memory:")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/fake-creds.json")
    monkeypatch.setattr(
        "casino_intel.cli.context.SheetsClient", lambda spreadsheet_id: sheets_client
    )
    fake_drive = DriveClient(service=_FakeDriveService(), root_folder_id="fake-root")
    monkeypatch.setattr("casino_intel.cli.context.DriveClient", lambda: fake_drive)
    return fake_service


def _run(args: list[str]):
    result = runner.invoke(app, args)
    assert result.exit_code == 0, f"{' '.join(args)} failed:\n{result.output}"
    return result


def _find_record_id(fake_service, sheet_name: str, match_column: str, match_value: str) -> str:
    header = SHEET_HEADERS[sheet_name]
    col = header.index(match_column)
    for row in fake_service.sheets[sheet_name][1:]:
        if len(row) > col and row[col] == match_value:
            return row[header.index("record_id")]
    raise AssertionError(f"No row in {sheet_name} with {match_column}={match_value!r}")


def test_full_quickstart_flow(fake_service, tmp_path):
    # Step 1: stand up the workbook.
    _run(
        ["initialise-workbook", "--owner", "Trevor", "--repository-url", "https://example.com/repo"]
    )
    assert set(fake_service.sheets.keys()) == set(TAB_NAMES)

    # Step 2: register the pilot brand set (a minimal slice for this smoke test),
    # using the same patched sheets_client/writer the CLI itself resolves to.
    from casino_intel.cli.context import AppContext
    from casino_intel.services.registry_service import RegistryService

    ctx = AppContext(dry_run=False)
    registry = RegistryService(ctx.writer)
    operator = registry.register_operator({"operator_name": "Example Group plc"}, actor="tester")
    brand = registry.register_brand(
        {
            "brand_name": "Example Casino",
            "operator_id": operator.record_id,
            "primary_domain": "example-casino.example",
            "brand_type": "casino_only",
            "sampling_rationale": "Quickstart smoke-test brand.",
        },
        actor="tester",
    )
    assert len(fake_service.sheets["Operators"]) == 2
    assert len(fake_service.sheets["Brands"]) == 2

    # Step 3: register and ingest a known regulator source (UKGC-style fixture).
    _run(
        [
            "add-source",
            "--url",
            "https://www.gamblingcommission.gov.uk/example",
            "--type",
            "regulator_statistics",
        ]
    )
    source_id = _find_record_id(
        fake_service, "Sources", "url", "https://www.gamblingcommission.gov.uk/example"
    )

    import_args = [
        "import-file",
        "--path",
        str(FIXTURE_PATH),
        "--source-id",
        source_id,
        "--importer",
        "ukgc",
        "--subject-id",
        "market_gb",
        "--period-start",
        "2025-01-01",
        "--period-end",
        "2025-12-31",
    ]
    _run(import_args)
    observations_after_first_import = len(fake_service.sheets["Observations"])
    assert observations_after_first_import > 1  # header + at least one new observation

    # Re-running against the same unchanged file must not duplicate rows (SC-005).
    _run(import_args)
    assert len(fake_service.sheets["Observations"]) == observations_after_first_import

    # Step 5: force + confirm a validation failure surfaces to Data Quality
    # (a metric that isn't in the registry).
    from casino_intel.services.observation_service import ObservationInput, ObservationService
    from casino_intel.sheets.config_loader import MetricRegistry
    from casino_intel.validation.data_quality import DataQualityWriter

    obs_service = ObservationService(
        ctx.writer, DataQualityWriter(ctx.sheets_client), MetricRegistry("config/metrics.yaml")
    )
    bad_result = obs_service.record_observation(
        ObservationInput(
            subject_type="brand",
            subject_id=brand.record_id,
            metric_id="not_a_real_metric",
            raw_value="123",
            source_id=source_id,
            evidence_type="third_party_estimate",
        ),
        actor="tester",
    )
    assert bad_result is None
    assert len(fake_service.sheets["Data Quality"]) >= 2

    # Step 6: human review — approve every unreviewed observation so `derive`
    # (Step 7) has approved inputs to read.
    from casino_intel.models.vocab import ReviewStatus
    from casino_intel.services.review_service import ReviewService

    review = ReviewService(ctx.sheets_client, ctx.change_log)
    header = SHEET_HEADERS["Observations"]
    review_col = header.index("review_status")
    id_col = header.index("record_id")
    for row in list(fake_service.sheets["Observations"][1:]):
        if row[review_col] == ReviewStatus.UNREVIEWED.value:
            record_id = row[id_col]
            review.mark_machine_checked("Observations", record_id, actor="tester")
            review.mark_human_reviewed("Observations", record_id, actor="tester")
            review.approve("Observations", record_id, actor="tester")

    # Step 7: run derivation — must not crash even if no compatible pairs
    # exist for this minimal fixture set (skip-don't-fabricate is correct).
    _run(["derive"])

    # Step 9: refresh the summary view.
    _run(["refresh-summary"])
    assert len(fake_service.sheets["Summary"]) >= 2  # header + at least our one brand

    # Step 10: export and verify no data loss for a couple of key tabs.
    _run(["export", "--output", str(tmp_path)])
    with open(tmp_path / "brands.csv", newline="", encoding="utf-8") as f:
        brand_rows = list(csv.reader(f))
    assert len(brand_rows) == len(fake_service.sheets["Brands"])

    # Research queue should be listable (even if empty) without error.
    _run(["research-queue", "list"])
