#!/usr/bin/env python3
"""Load researched operator financials (from /tmp/financials.json) as Observations.

Input JSON is a list of per-operator records:
[
  {
    "operator_id": "operator_...",
    "company": "Flutter Entertainment plc",
    "primary_source_url": "https://...",
    "source_type": "corporate_press_release",   # a SourceType value
    "period_start": "2024-01-01", "period_end": "2024-12-31",
    "figures": [
      {"metric_id": "revenue", "amount_millions": 14048, "currency": "USD",
       "is_estimate": false, "source_url": "https://..."},
      {"metric_id": "active_customers", "amount_absolute": 13898000,
       "is_estimate": false, "note": "AMPs", "source_url": "https://..."}
    ]
  }
]

Each money figure is recorded in its reported currency (raw) and normalised to GBP
via the static placeholder FX table (documented as such — normalisation/currency.py),
retaining raw value + fx rate per FR-005. Records subject_type=operator,
evidence_type=reported_primary (or third_party_estimate when is_estimate=true),
review_status=unreviewed. Idempotent by fingerprint (subject/metric/period/source/value).

Run from the repo root. Requires GOOGLE_APPLICATION_CREDENTIALS + SPREADSHEET_ID.

Usage:
    python scripts/import_operator_financials.py --path /tmp/financials.json [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime

from casino_intel.cli.context import AppContext
from casino_intel.models.ids import new_id
from casino_intel.models.source import Source
from casino_intel.models.vocab import SourceType
from casino_intel.services.observation_service import ObservationInput, ObservationService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS
from casino_intel.sheets.serialization import to_sheet_record

ACTOR = "import_operator_financials"

# agent metric name -> registry metric_id
_METRIC_MAP = {
    "revenue": "revenue",
    "gross_gaming_revenue": "ggr",
    "net_gaming_revenue": "ngr",
    "adjusted_ebitda": "adjusted_ebitda",
    "operating_profit": "operating_profit",
    "net_profit": "net_profit",
    "sales_and_marketing_expense": "sales_and_marketing_expense",
    "marketing_expense": "marketing_expense",
    "active_customers": "active_customers",
}


def _get_or_create_source(ctx: AppContext, url: str, source_type: str, title: str) -> str:
    header = SHEET_HEADERS["Sources"]
    id_col, url_col = header.index("record_id"), header.index("url")
    rows = ctx.sheets_client.batch_get_values(["Sources!A2:ZZ"]).get("Sources!A2:ZZ", [])
    for row in rows:
        if len(row) > url_col and row[url_col] == url:
            return row[id_col]
    now = datetime.now(UTC)
    try:
        st = SourceType(source_type)
    except ValueError:
        st = SourceType.CORPORATE_PRESS_RELEASE
    src = Source(
        record_id=new_id("source"), created_at=now, created_by=ACTOR, updated_at=now,
        source_type=st, url=url, title=title, is_primary_source=True,
    )
    row = to_sheet_record(src.model_dump(mode="json"), header)
    return ctx.writer.append_record(
        "Sources", row, actor=ACTOR, ingestion_run_id=ctx.ingestion_run_id
    ).record_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    companies = json.load(open(args.path))
    ctx = AppContext(dry_run=args.dry_run, actor=ACTOR)
    svc = ObservationService(ctx.writer, ctx.data_quality, ctx.metric_registry)

    new = dup = rejected = 0
    for co in companies:
        opid = co["operator_id"]
        src_id = _get_or_create_source(
            ctx, co["primary_source_url"], co.get("source_type", "corporate_press_release"),
            f"{co['company']} financial results {co.get('period_end','')}",
        )
        for f in co.get("figures", []):
            metric_id = _METRIC_MAP.get(f["metric"], f["metric"])
            is_est = bool(f.get("is_estimate"))
            if "amount_absolute" in f:  # customer counts etc. — no currency
                amount, currency, unit = float(f["amount_absolute"]), "", "customers"
            else:
                amount, currency = float(f["amount_millions"]) * 1_000_000, f.get("currency", "")
                unit = currency
            note = "FY figure from published results. " + (f.get("note", "") or "")
            if currency:
                note += " Normalised to GBP via static placeholder FX rate (approximate)."
            result = svc.record_observation(
                ObservationInput(
                    subject_type="operator", subject_id=opid, metric_id=metric_id,
                    raw_value=str(int(amount)) if amount == int(amount) else str(amount),
                    raw_unit=unit, normalised_numeric_value=amount, currency=currency,
                    source_id=src_id,
                    evidence_type="third_party_estimate" if is_est else "reported_primary",
                    confidence="low" if is_est else "high",
                    period_start=co.get("period_start"), period_end=co.get("period_end"),
                    # dates the FX rate to the reporting period end (required when
                    # a currency conversion to GBP happens)
                    as_of_date=co.get("period_end"),
                    segment=f.get("segment", ""),
                    methodology_note=note.strip(), created_by=ACTOR,
                ),
                actor=ACTOR, ingestion_run_id=ctx.ingestion_run_id,
            )
            if result is None:
                rejected += 1
                print(f"  REJECTED {co['company']} / {metric_id} (see Data Quality)")
            elif result.duplicate:
                dup += 1
            else:
                new += 1
        print(f"{co['company']}: processed {len(co.get('figures',[]))} figures")

    print(f"\nDone: {new} new, {dup} duplicate, {rejected} rejected."
          + (" [dry-run]" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
