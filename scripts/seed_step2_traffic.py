#!/usr/bin/env python3
"""Seed the Step 2 append-only demonstration (quickstart.md Step 2, FR-004/SC-005).

Adds ONE traffic-estimate observation for a single brand on TWO different
`as_of_date`s, then re-adds the first one. Because the Observation fingerprint
(validation/fingerprint.py) includes `as_of_date`, the two dated rows have
distinct fingerprints and BOTH persist in `Observations` (proving append-only,
FR-004), while the repeated third write collides on fingerprint and is skipped
(proving idempotency, SC-005).

It writes through the same validated, deduplicating path the real ingestion
pipeline uses (`ObservationService` -> append-only `SheetsWriter`), so a passing
run also exercises the metric-registry check and the missing-source guard.

Prerequisites: run `scripts/seed_pilot_brands.py` first (the target brand must
already exist in `Brands`). Run from the repo root so `config/metrics.yaml`
resolves. Requires GOOGLE_APPLICATION_CREDENTIALS + SPREADSHEET_ID (see .env).

Usage:
    python scripts/seed_step2_traffic.py [--brand-domain betway.com]
                                         [--metric estimated_monthly_visits]
                                         [--raw-value 12500000]
                                         [--as-of 2026-05-31 --as-of 2026-06-30]
                                         [--dry-run]
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from casino_intel.cli.context import AppContext
from casino_intel.models.ids import new_id
from casino_intel.models.source import Source
from casino_intel.models.vocab import SourceType
from casino_intel.services.observation_service import ObservationInput, ObservationService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.serialization import to_sheet_record

ACTOR = "seed_step2_traffic"

# A stable, clearly-synthetic source URL so re-runs reuse one Source row rather
# than registering a duplicate each time.
SEED_SOURCE_URL = "seed://step2/traffic-estimate-demo"
SEED_SOURCE_TITLE = "Step 2 append-only demo — synthetic traffic estimate"

BRANDS_SHEET = "Brands"
SOURCES_SHEET = "Sources"

DEFAULT_AS_OF_DATES = ["2026-05-31", "2026-06-30"]


def _rows(context: AppContext, sheet: str) -> list[list[str]]:
    rng = f"{sheet}!A2:ZZ"
    return context.sheets_client.batch_get_values([rng]).get(rng, [])


def find_brand(context: AppContext, domain: str) -> tuple[str, str]:
    """Return (record_id, brand_name) for the brand whose primary_domain matches."""
    header = SHEET_HEADERS[BRANDS_SHEET]
    id_col = header.index("record_id")
    name_col = header.index("brand_name")
    domain_col = header.index("primary_domain")
    for row in _rows(context, BRANDS_SHEET):
        if len(row) > domain_col and row[domain_col].strip().lower() == domain.strip().lower():
            return row[id_col], row[name_col]
    raise SystemExit(
        f"No brand with primary_domain {domain!r} found in {BRANDS_SHEET!r}. "
        "Run scripts/seed_pilot_brands.py first, or pass --brand-domain."
    )


def get_or_create_source(context: AppContext) -> str:
    """Reuse the seed Source if already present (idempotent), else register it."""
    header = SHEET_HEADERS[SOURCES_SHEET]
    id_col = header.index("record_id")
    url_col = header.index("url")
    for row in _rows(context, SOURCES_SHEET):
        if len(row) > url_col and row[url_col] == SEED_SOURCE_URL:
            return row[id_col]

    now = datetime.now(UTC)
    source = Source(
        record_id=new_id("source"),
        created_at=now,
        created_by=ACTOR,
        updated_at=now,
        source_type=SourceType.TRAFFIC_INTELLIGENCE,
        url=SEED_SOURCE_URL,
        title=SEED_SOURCE_TITLE,
        publisher="(seed script)",
        territory="GB",
        notes=(
            "Synthetic source created only to satisfy the FR-004 "
            "append-only demo in quickstart Step 2."
        ),
    )
    row = to_sheet_record(source.model_dump(mode="json"), header)
    result = context.writer.append_record(
        SOURCES_SHEET, row, actor=ACTOR, ingestion_run_id=context.ingestion_run_id
    )
    return result.record_id


def _observation_input(
    *, subject_id: str, metric: str, raw_value: str, source_id: str, as_of: str
) -> ObservationInput:
    return ObservationInput(
        subject_type="brand",
        subject_id=subject_id,
        metric_id=metric,
        raw_value=raw_value,
        raw_unit="visits",
        source_id=source_id,
        evidence_type="third_party_estimate",
        confidence="low",
        as_of_date=as_of,
        geography="GB",
        source_locator="seed-script/demo",
        verbatim_excerpt=f"Estimated monthly visits as of {as_of}: {raw_value}.",
        methodology_note=(
            "Synthetic value for the FR-004/SC-005 append-only + idempotency demonstration."
        ),
        created_by=ACTOR,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brand-domain", default="bet365.com")
    parser.add_argument("--metric", default="estimated_monthly_visits")
    parser.add_argument("--raw-value", default="12500000")
    parser.add_argument(
        "--as-of",
        action="append",
        dest="as_of_dates",
        help="ISO date; pass twice for the two-date demo. Defaults to two month-ends.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    as_of_dates = args.as_of_dates or DEFAULT_AS_OF_DATES
    if len(as_of_dates) < 2:
        parser.error("Provide at least two --as-of dates (or omit to use the defaults).")

    context = AppContext(dry_run=args.dry_run, actor=ACTOR)
    brand_id, brand_name = find_brand(context, args.brand_domain)
    source_id = get_or_create_source(context)
    print(f"Target brand : {brand_name} ({brand_id})")
    print(f"Source       : {source_id}")
    print(f"Metric       : {args.metric}   raw_value={args.raw_value}")

    service = ObservationService(
        context.writer, context.data_quality, context.metric_registry
    )

    written = 0
    for as_of in as_of_dates:
        result = service.record_observation(
            _observation_input(
                subject_id=brand_id,
                metric=args.metric,
                raw_value=args.raw_value,
                source_id=source_id,
                as_of=as_of,
            ),
            actor=ACTOR,
            ingestion_run_id=context.ingestion_run_id,
        )
        if result is None:
            print(f"  as_of={as_of}: REJECTED (see Data Quality tab) — unexpected for this demo")
        elif result.duplicate:
            print(
                f"  as_of={as_of}: duplicate, skipped "
                f"(fingerprint already present) -> {result.record_id}"
            )
        else:
            written += 1
            print(f"  as_of={as_of}: appended -> {result.record_id}")

    # Idempotency proof: repeat the first date; should collide and be skipped.
    repeat = service.record_observation(
        _observation_input(
            subject_id=brand_id,
            metric=args.metric,
            raw_value=args.raw_value,
            source_id=source_id,
            as_of=as_of_dates[0],
        ),
        actor=ACTOR,
        ingestion_run_id=context.ingestion_run_id,
    )
    repeat_dupe = repeat is not None and repeat.duplicate
    repeat_msg = (
        "deduped as expected (idempotent)"
        if repeat_dupe
        else "NOT deduped — check fingerprint store"
    )
    print(f"  repeat as_of={as_of_dates[0]}: {repeat_msg}")

    mode = " [dry-run: nothing written]" if args.dry_run else ""
    print(f"\nDone. {written} distinct dated observation(s) appended for {brand_name}.{mode}")
    print(
        "Verify in the Observations tab: two rows for this brand/metric, "
        "differing only by as_of_date."
    )


if __name__ == "__main__":
    main()
