"""`casino-intel validate` (contracts/cli-commands.md): re-run business-rule
validation (FR-020) across existing `active` Observation records without
re-ingesting, refreshing Data Quality. Never mutates Observations/Brands/etc.
"""

from __future__ import annotations

import typer

from casino_intel.cli.context import AppContext
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.validation import rules_core, rules_ingestion

OBSERVATIONS_SHEET = "Observations"


def validate(ctx: typer.Context) -> None:
    context: AppContext = ctx.obj

    header = SHEET_HEADERS[OBSERVATIONS_SHEET]
    try:
        rows = context.sheets_client.batch_get_values([f"{OBSERVATIONS_SHEET}!A2:ZZ"]).get(
            f"{OBSERVATIONS_SHEET}!A2:ZZ", []
        )
    except Exception as exc:  # noqa: BLE001 - a run-level failure, distinct from per-record issues
        typer.echo(f"Could not read {OBSERVATIONS_SHEET!r}: {exc}")
        raise typer.Exit(code=1) from None

    issues_found = 0
    for row in rows:
        record = dict(zip(header, row, strict=False))
        if not record or record.get("status") not in (None, "", "active"):
            continue

        failures = []
        failures += rules_core.validate_has_source(record.get("source_id"))
        failures += rules_core.validate_metric_known(
            record.get("metric_id", ""), context.metric_registry
        )
        raw_value = record.get("raw_value", "")
        normalised_raw = record.get("normalised_numeric_value") or ""
        normalised_value = float(normalised_raw) if normalised_raw not in ("", None) else None
        failures += rules_core.validate_normalised_requires_raw(raw_value, normalised_value)
        failures += rules_ingestion.validate_not_stale(record.get("as_of_date") or None)

        for issue_type, description in failures:
            context.data_quality.raise_issue(
                issue_type=issue_type,
                sheet_name=OBSERVATIONS_SHEET,
                record_id=record.get("record_id", ""),
                field_name=record.get("metric_id", ""),
                description=description,
            )
            issues_found += 1

    typer.echo(f"Validation complete: {issues_found} data-quality issue(s) raised.")
