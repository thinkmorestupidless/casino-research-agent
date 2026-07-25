#!/usr/bin/env python3
"""Regenerate the human-readable Financials view tab from the canonical data.

Financial figures are stored canonically as operator-subject rows in the
Observations tab (keyed by operator_id ULID), and ratios in Derived Metrics —
neither is easy to read. This projects both onto the purpose-built Financials
tab with the operator NAME on every row (in comparability_note), so the numbers
are legible where you'd expect them.

Overwrites the Financials tab wholesale (like refresh-summary does for Summary):
it's a generated view, not an append-only fact store. Re-run any time to refresh.

Run from the repo root. Requires GOOGLE_APPLICATION_CREDENTIALS + SPREADSHEET_ID.

Usage:
    python scripts/build_financials_view.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from casino_intel.cli.context import AppContext
from casino_intel.models.ids import new_id
from casino_intel.sheets.safety import escape_rows
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

FINANCIALS = "Financials"
_PCT_METRICS = {"adjusted_ebitda_margin", "marketing_pct_revenue"}


def _rows(ctx: AppContext, sheet: str) -> list[list[str]]:
    rng = f"{sheet}!A2:BZ"
    return ctx.sheets_client.batch_get_values([rng]).get(rng, [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    ctx = AppContext(dry_run=args.dry_run, actor="build_financials_view")
    oh = SHEET_HEADERS["Operators"]
    obh = SHEET_HEADERS["Observations"]
    dh = SHEET_HEADERS["Derived Metrics"]
    fh = SHEET_HEADERS[FINANCIALS]

    opname = {
        r[0]: r[oh.index("operator_name")]
        for r in _rows(ctx, "Operators")
        if r and r[0].strip()
    }

    def og(r, hdr, n):
        i = hdr.index(n)
        return r[i] if i < len(r) else ""

    now = datetime.now(UTC).isoformat()
    out_rows: list[dict] = []

    # Reported figures (operator-subject observations)
    for r in _rows(ctx, "Observations"):
        if not r or not r[0].strip() or og(r, obh, "subject_type") != "operator":
            continue
        name = opname.get(og(r, obh, "subject_id"), og(r, obh, "subject_id"))
        est = og(r, obh, "evidence_type") == "third_party_estimate"
        period = f"{og(r, obh, 'period_start')}..{og(r, obh, 'period_end')}"
        seg = og(r, obh, "segment")
        out_rows.append(
            {
                "record_id": new_id("financial"),
                "created_at": now, "created_by": "build_financials_view", "updated_at": now,
                "status": "active", "notes": og(r, obh, "methodology_note"),
                "source_id": og(r, obh, "source_id"),
                "evidence_type": og(r, obh, "evidence_type"),
                "confidence": og(r, obh, "confidence"),
                "review_status": og(r, obh, "review_status"),
                "period_start": og(r, obh, "period_start"),
                "period_end": og(r, obh, "period_end"),
                "operator_id": og(r, obh, "subject_id"),
                "financial_metric": og(r, obh, "metric_id"),
                "raw_value": og(r, obh, "raw_value"),
                "raw_currency": og(r, obh, "currency"),
                "normalised_value_gbp": og(r, obh, "normalised_numeric_value"),
                "segment": seg,
                "reported_or_derived": "estimate" if est else "reported",
                "comparability_note": f"{name} — {period}" + (f" [{seg}]" if seg else ""),
            }
        )

    # Derived ratios (Derived Metrics tab)
    for r in _rows(ctx, "Derived Metrics"):
        if not r or not r[0].strip() or og(r, dh, "subject_type") != "operator":
            continue
        name = opname.get(og(r, dh, "subject_id"), og(r, dh, "subject_id"))
        metric = og(r, dh, "metric_id")
        val = og(r, dh, "value")
        period = f"{og(r, dh, 'period_start')}..{og(r, dh, 'period_end')}"
        out_rows.append(
            {
                "record_id": new_id("financial"),
                "created_at": now, "created_by": "build_financials_view", "updated_at": now,
                "status": "active", "notes": og(r, dh, "assumptions"),
                "confidence": og(r, dh, "confidence"),
                "review_status": og(r, dh, "review_status"),
                "period_start": og(r, dh, "period_start"),
                "period_end": og(r, dh, "period_end"),
                "operator_id": og(r, dh, "subject_id"),
                "financial_metric": metric,
                "raw_value": val,
                "raw_currency": "%" if metric in _PCT_METRICS else "GBP",
                "normalised_value_gbp": val,
                "reported_or_derived": "derived",
                "comparability_note": f"{name} — {period} (derived)",
            }
        )

    grid = [[str(row.get(col, "")) for col in fh] for row in out_rows]
    print(f"Financials view rows to write: {len(grid)}")
    if not args.dry_run:
        # clear then overwrite (generated view, not append-only)
        ctx.sheets_client._service.spreadsheets().values().clear(
            spreadsheetId=ctx.spreadsheet_id, range=f"{FINANCIALS}!A2:ZZ", body={}
        ).execute()
        if grid:
            ctx.sheets_client.batch_update_values(
                [{"range": f"{FINANCIALS}!A2", "values": escape_rows(grid)}]
            )
        print(f"  wrote {len(grid)} rows to {FINANCIALS}")
    else:
        print("[dry-run] nothing written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
