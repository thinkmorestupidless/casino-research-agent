#!/usr/bin/env python3
"""Create Brand rows from the Anjouan (ALSI) register domains.

Follow-on to scripts/import_anjouan_register.py (which loaded operators +
licences). The register lists domains per licensee but not the brand vertical,
so brand_type is INFERRED from domain keywords where there's a hint and left as
'unknown' otherwise — the inference is unverified and flagged in each brand's
notes. Each domain becomes one Brand linked to its licensee's operator.

Idempotent by primary_domain; chunked batched appends.

Run from the repo root. Requires GOOGLE_APPLICATION_CREDENTIALS + SPREADSHEET_ID
and an existing --source-id (the Anjouan register source).

Usage:
    python scripts/import_anjouan_brands.py --source-id source_XXX [--chunk 500] [--dry-run]
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

ACTOR = "import_anjouan_brands"
REGISTER_URL = "https://anjouangaming.com/license-register/"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/126 Safari/537.36"
    )
}
_DATA_RE = re.compile(r'<script type="application/json" id="ag-licence-data">(.*?)</script>', re.S)

# Ordered by priority: first match wins. Keyword hints only — unverified.
_TYPE_KEYWORDS = [
    ("bingo_led", ("bingo",)),
    ("crypto", ("crypto", "coin", "btc", "chain", "token")),
    ("casino_only", ("casino", "slot", "spin", "vegas", "jackpot")),
    ("sportsbook_led", ("bet", "sport", "book", "odds", "pari")),
]


def _infer_type(domain: str) -> tuple[str, bool]:
    """Return (brand_type, inferred?). inferred=False means we fell back to unknown."""
    s = domain.lower()
    for btype, kws in _TYPE_KEYWORDS:
        if any(k in s for k in kws):
            return btype, True
    return "unknown", False


def _split_domains(s: str) -> list[str]:
    parts = re.split(r"[,\s;/]+", s or "")
    return [x.strip().lower() for x in parts if "." in x and " " not in x.strip()]


def _fetch() -> list[dict]:
    html = httpx.get(REGISTER_URL, headers=UA, follow_redirects=True, timeout=90).text
    return json.loads(_DATA_RE.search(html).group(1))


def _read_operator_name_to_id(ctx: AppContext) -> dict[str, str]:
    header = SHEET_HEADERS["Operators"]
    id_idx, name_idx = header.index("record_id"), header.index("operator_name")
    rows = ctx.sheets_client.batch_get_values(["Operators!A2:ZZ"]).get("Operators!A2:ZZ", [])
    out: dict[str, str] = {}
    for row in rows:
        if len(row) > max(id_idx, name_idx) and row[name_idx].strip():
            out.setdefault(row[name_idx].strip(), row[id_idx].strip())
    return out


def _read_existing_domains(ctx: AppContext) -> set[str]:
    header = SHEET_HEADERS["Brands"]
    idx = header.index("primary_domain")
    rows = ctx.sheets_client.batch_get_values(["Brands!A2:ZZ"]).get("Brands!A2:ZZ", [])
    return {row[idx].strip().lower() for row in rows if len(row) > idx and row[idx].strip()}


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--chunk", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    ctx = AppContext(dry_run=args.dry_run, actor=ACTOR)
    data = _fetch()
    name_to_opid = _read_operator_name_to_id(ctx)
    existing_domains = _read_existing_domains(ctx)

    # domain -> operator_id (first licensee that lists it)
    domain_op: dict[str, str] = {}
    unmapped = 0
    for d in data:
        opid = name_to_opid.get((d.get("company") or "").strip())
        for dm in _split_domains(d.get("domains", "")):
            if dm in domain_op or dm in existing_domains:
                continue
            if not opid:
                unmapped += 1
                continue
            domain_op[dm] = opid

    brand_fields = []
    inferred_count = 0
    for dm, opid in domain_op.items():
        btype, inferred = _infer_type(dm)
        inferred_count += inferred
        brand_fields.append(
            {
                "brand_name": dm.split(".")[0],
                "primary_domain": dm,
                "operator_id": opid,
                "brand_type": btype,
                "source_id": args.source_id,  # provenance
                "notes": (
                    "Anjouan register domain; brand_type "
                    + ("inferred from domain keywords (unverified)" if inferred else "unknown")
                ),
            }
        )

    print(
        f"Domains -> new brands: {len(brand_fields)} "
        f"(inferred type: {inferred_count}, unknown: {len(brand_fields) - inferred_count}; "
        f"{unmapped} domains skipped — operator not found)"
    )
    if not args.dry_run and brand_fields:
        service = RegistryService(ctx.writer)
        total = 0
        for chunk in _chunks(brand_fields, args.chunk):
            total += len(
                service.register_brands(chunk, actor=ACTOR, ingestion_run_id=ctx.ingestion_run_id)
            )
        print(f"  wrote {total} brands")
    if args.dry_run:
        print("[dry-run] nothing written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
