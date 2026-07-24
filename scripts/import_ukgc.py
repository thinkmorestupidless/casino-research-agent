#!/usr/bin/env python3
"""Import a UKGC industry-statistics XLSX export into the Observations
sheet (User Story 2, T055).

Usage:
    python scripts/import_ukgc.py --path FILE --source-id SOURCE_ID \\
        --subject-id MARKET_SUBJECT_ID --period-start YYYY-MM-DD \\
        --period-end YYYY-MM-DD [--dry-run]

Runs the standard fetch(skipped)->archive->parse->extract->normalise->
validate->dedup->append pipeline (`services/ingestion_run.py`) against a
locally-supplied file, exactly like `casino-intel import-file` but as a
standalone script for the specific UKGC statistics shape.
"""

from __future__ import annotations

import argparse
import sys
from functools import partial
from pathlib import Path

from casino_intel.cli.context import AppContext
from casino_intel.fetching.archiver import DocumentArchiver
from casino_intel.fetching.fetcher import Fetcher
from casino_intel.parsing.ukgc_importer import extract_ukgc_xlsx
from casino_intel.services.ingestion_run import IngestionOutcome, IngestionRun
from casino_intel.services.observation_service import ObservationService

ACTOR = "import_ukgc"


def run(
    context: AppContext,
    *,
    path: Path,
    source_id: str,
    subject_id: str,
    period_start: str,
    period_end: str,
) -> IngestionOutcome:
    source = _load_source(context, source_id)

    archiver = DocumentArchiver(context.drive_client, context.fingerprint_store, context.writer)
    observation_service = ObservationService(
        context.writer, context.data_quality, context.metric_registry
    )
    ingestion = IngestionRun(
        fetcher=Fetcher(),
        archiver=archiver,
        observation_service=observation_service,
        data_quality=context.data_quality,
        metric_registry=context.metric_registry,
    )

    extract_fn = partial(
        lambda content, content_type: extract_ukgc_xlsx(
            content,
            source_id=source_id,
            subject_id=subject_id,
            period_start=period_start,
            period_end=period_end,
        )
    )
    content = path.read_bytes()
    return ingestion.run(
        source=source,
        extract_fn=extract_fn,
        relative_folder="sources/regulators",
        actor=ACTOR,
        ingestion_run_id=context.ingestion_run_id,
        content=content,
        content_type=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        filename=path.name,
    )


def _load_source(context: AppContext, source_id: str):
    from casino_intel.models.source import Source
    from casino_intel.sheets.schema_definitions import SHEET_HEADERS

    header = SHEET_HEADERS["Sources"]
    rows = context.sheets_client.batch_get_values(["Sources!A2:ZZ"]).get("Sources!A2:ZZ", [])
    id_col = header.index("record_id")
    for row in rows:
        if len(row) > id_col and row[id_col] == source_id:
            record = dict(zip(header, row, strict=False))
            return Source(**record)
    raise LookupError(f"source_id {source_id!r} not found in Sources sheet")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--period-start", required=True)
    parser.add_argument("--period-end", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    context = AppContext(dry_run=args.dry_run)
    outcome = run(
        context,
        path=args.path,
        source_id=args.source_id,
        subject_id=args.subject_id,
        period_start=args.period_start,
        period_end=args.period_end,
    )
    print(
        f"UKGC import complete: {outcome.new_observations} new, "
        f"{outcome.duplicate_observations} duplicate, "
        f"{outcome.data_quality_issues} data-quality issues, "
        f"errors={outcome.errors}"
    )
    return 0 if not outcome.errors else 1


if __name__ == "__main__":
    sys.exit(main())
