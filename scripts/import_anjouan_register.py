#!/usr/bin/env python3
"""Bulk-import the full Anjouan (ALSI) licence register as Operators + Licences.

The Anjouan public register (https://anjouangaming.com/license-register/) embeds
its entire dataset as JSON in a <script id="ag-licence-data"> tag, so no scraping
or pagination is needed — parse it directly.

Models each register entry as (spec/data-model): one Operator per licensee
company + one Licence per entry. We deliberately do NOT create Brand rows: the
register only supplies domains, not the brand vertical (Brand.brand_type is
required and unknown), so domains are recorded in each licence's notes instead.

Writes in chunks (batched appends) to stay well within request-size limits, and
is idempotent: operators are deduped by name and licences by licence number, so
re-running refreshes without duplicating.

Run from the repo root. Requires GOOGLE_APPLICATION_CREDENTIALS + SPREADSHEET_ID
and an existing --source-id for provenance.

Usage:
    python scripts/import_anjouan_register.py --source-id source_XXX \
        [--chunk 500] [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import sys

import httpx

from casino_intel.cli.context import AppContext
from casino_intel.services.registry_service import RegistryService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

ACTOR = "import_anjouan_register"
REGISTER_URL = "https://anjouangaming.com/license-register/"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/126 Safari/537.36"
    )
}
REGULATOR = "Anjouan Gaming Authority (ALSI)"
JURISDICTION = "Anjouan"

_STATUS_MAP = {
    "valid": "active",
    "suspended": "suspended",
    "revoked": "revoked",
    "expired": "surrendered",
}


_DATA_RE = re.compile(r'<script type="application/json" id="ag-licence-data">(.*?)</script>', re.S)


def _fetch_register() -> list[dict]:
    html = httpx.get(REGISTER_URL, headers=UA, follow_redirects=True, timeout=90).text
    m = _DATA_RE.search(html)
    if not m:
        raise SystemExit("Could not find embedded ag-licence-data JSON in the register page.")
    return json.loads(m.group(1))


def _read_col(ctx: AppContext, sheet: str, col: str) -> set[str]:
    header = SHEET_HEADERS[sheet]
    idx = header.index(col)
    rng = f"{sheet}!A2:ZZ"
    rows = ctx.sheets_client.batch_get_values([rng]).get(rng, [])
    return {row[idx].strip() for row in rows if len(row) > idx and row[idx].strip()}


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--chunk", type=int, default=500)
    parser.add_argument("--limit", type=int, default=0, help="Process first N entries only.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    ctx = AppContext(dry_run=args.dry_run, actor=ACTOR)
    data = _fetch_register()
    if args.limit:
        data = data[: args.limit]
    print(f"Register entries: {len(data)}")

    existing_ops = _read_col(ctx, "Operators", "operator_name")  # names already present
    existing_lics = _read_col(ctx, "Licences", "official_licence_number")

    # Unique new companies -> Operators
    seen = set()
    new_companies = []
    for d in data:
        name = (d.get("company") or "").strip()
        if not name or name in existing_ops or name in seen:
            continue
        seen.add(name)
        new_companies.append(name)

    service = RegistryService(ctx.writer)
    company_to_opid: dict[str, str] = {}

    dup = len(existing_ops & {(d.get("company") or "").strip() for d in data})
    print(f"New operators to create: {len(new_companies)} (skipping {dup} already present)")
    if not args.dry_run:
        for chunk in _chunks(new_companies, args.chunk):
            fields = [{"operator_name": n, "source_id": args.source_id} for n in chunk]
            results = service.register_operators(
                fields, actor=ACTOR, ingestion_run_id=ctx.ingestion_run_id
            )
            for n, r in zip(chunk, results, strict=True):
                company_to_opid[n] = r.record_id
        print(f"  wrote {len(company_to_opid)} operators")

    # Licences (skip those already present by number)
    licence_fields = []
    skipped_existing = 0
    for d in data:
        num = (d.get("number") or "").strip()
        if not num or num in existing_lics:
            skipped_existing += 1
            continue
        name = (d.get("company") or "").strip()
        opid = company_to_opid.get(name)  # None in dry-run or for pre-existing operators
        licence_fields.append(
            {
                "operator_id": opid or "",
                "regulator": REGULATOR,
                "jurisdiction": JURISDICTION,
                "official_licence_number": num,
                "licence_type": "other",  # register axis is b2c/b2b, not our activity enum
                "licence_status": _STATUS_MAP.get((d.get("status") or "").lower(), "unknown"),
                "effective_date": (d.get("issued") or None),
                "expiry_date": (d.get("expiry") or None),
                "licensee_legal_name": name,
                "source_id": args.source_id,
                "notes": (
                    f"Anjouan ALSI; register_type={d.get('type', '')}; "
                    f"domains={d.get('domains', '')}"
                ),
            }
        )

    print(f"New licences to write: {len(licence_fields)} (skipping {skipped_existing} existing)")
    if not args.dry_run and licence_fields:
        total = 0
        for chunk in _chunks(licence_fields, args.chunk):
            results = service.register_licences(
                chunk, actor=ACTOR, ingestion_run_id=ctx.ingestion_run_id
            )
            total += len(results)
        print(f"  wrote {total} licences")
    if args.dry_run:
        print("[dry-run] nothing written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
