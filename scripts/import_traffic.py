#!/usr/bin/env python3
"""Import a brand-traffic provider CSV/XLSX export (quickstart Step 4, the
"structured traffic export" format; spec FR-025, data-model.md "Traffic").

`import_traffic_rows` is not an `extract_fn` (it writes both the Traffic view
row and canonical Observations, one comparability-group per provider), so it
has no `import-file`/`ingest-source` CLI path — this script is its entry point,
mirroring `scripts/import_ukgc.py`. It archives the export as a Document, then
records observations (`evidence_type=third_party_estimate`) linked to it.

Run from the repo root so config/metrics.yaml resolves. Requires an existing
--source-id (FR-011: every fact traces to a source) and, because brand_ids are
workbook-specific ULIDs, a --brand-id to attach the rows to a real seeded brand
(overrides the CSV's brand_id column for every row).

Usage:
    python scripts/import_traffic.py --path scripts/traffic_export_demo.csv \\
        --source-id source_XXX --brand-id brand_YYY [--provider similarweb] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from casino_intel.cli.context import AppContext
from casino_intel.fetching.archiver import DocumentArchiver
from casino_intel.models.source import Source
from casino_intel.parsing.traffic_importer import import_traffic_rows
from casino_intel.services.observation_service import ObservationService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

ACTOR = "import_traffic"


def _load_source(context: AppContext, source_id: str) -> Source:
    header = SHEET_HEADERS["Sources"]
    rows = context.sheets_client.batch_get_values(["Sources!A2:ZZ"]).get("Sources!A2:ZZ", [])
    id_col = header.index("record_id")
    for row in rows:
        if len(row) > id_col and row[id_col] == source_id:
            record = dict(zip(header, row, strict=False))
            record.pop("record_id")
            return Source(record_id=source_id, **{k: v for k, v in record.items() if v != ""})
    raise SystemExit(f"source_id {source_id!r} not found in Sources sheet")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--source-id", required=True)
    parser.add_argument(
        "--brand-id",
        default="",
        help="Real seeded brand_id to attach every row to (overrides the CSV column).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.path.exists():
        raise SystemExit(f"File not found: {args.path}")

    context = AppContext(dry_run=args.dry_run, actor=ACTOR)
    source = _load_source(context, args.source_id)

    content = args.path.read_bytes()
    table = pd.read_csv(args.path)
    if args.brand_id:
        table["brand_id"] = args.brand_id

    # Archive the export as a Document so observations link back to the file.
    archiver = DocumentArchiver(context.drive_client, context.fingerprint_store, context.writer)
    archive_result = archiver.archive_fetch(
        source_id=source.record_id,
        filename=args.path.name,
        content=content,
        mime_type="text/csv",
        actor=ACTOR,
        ingestion_run_id=context.ingestion_run_id,
        relative_folder="sources/traffic",
    )

    observation_service = ObservationService(
        context.writer, context.data_quality, context.metric_registry
    )
    created = import_traffic_rows(
        table,
        source_id=source.record_id,
        writer=context.writer,
        observation_service=observation_service,
        actor=ACTOR,
        ingestion_run_id=context.ingestion_run_id,
        document_id=archive_result.document_id,
    )
    print(
        f"Traffic import complete: {len(created)} new Traffic row(s) "
        f"(document={archive_result.document_id}, new_version={archive_result.is_new_version})"
        + (" [dry-run]" if args.dry_run else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
