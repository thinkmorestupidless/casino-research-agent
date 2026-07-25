#!/usr/bin/env python3
"""Import the Malta Gaming Authority (MGA) licensee register as Operators + Licences.

The MGA register SPA (https://mgalicenseeregister.mga.org.mt/) serves an
ENCRYPTED API payload that the front-end decrypts client-side (a deliberate
anti-bulk-scraping measure). We do NOT decrypt that payload; instead we read the
rendered public results table via a headless browser (what any visitor sees),
paging through the client-side paginator with a polite delay. Run only with the
data owner's authorisation.

Models each licensee as one Operator (company, Malta registration number) + one
Licence per MGA authorisation number (jurisdiction=MT). No Brand rows: the list
view exposes no domains. Chunked, idempotent (operators by name, licences by
number), so re-runs refresh.

Note: the list view does not itemise per-authorisation status, so licence_status
is recorded as "active" (these are entries in the live public register) with a
caveat in notes — verify individual statuses via the MGA dynamic seal if needed.

Run from the repo root. Requires GOOGLE_APPLICATION_CREDENTIALS + SPREADSHEET_ID
and an existing --source-id.

Usage:
    python scripts/import_mga_register.py --source-id source_XXX [--chunk 500] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
import time

from playwright.sync_api import sync_playwright

from casino_intel.cli.context import AppContext
from casino_intel.services.registry_service import RegistryService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

ACTOR = "import_mga_register"
REGISTER_URL = "https://mgalicenseeregister.mga.org.mt/"
REGULATOR = "Malta Gaming Authority"
JURISDICTION = "MT"
_LABELS = {
    "Company Name": "company",
    "Registration Number": "reg",
    "Authorisation Number": "auth",
    "Authorisation type": "type",
}


def _parse_card(text: str) -> dict:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    out: dict[str, str] = {}
    for i, ln in enumerate(lines):
        if ln in _LABELS and i + 1 < len(lines):
            out[_LABELS[ln]] = lines[i + 1]
    return out


def scrape_register(max_pages: int = 60, delay_s: float = 0.8) -> list[dict]:
    records: dict[str, dict] = {}  # auth -> record (dedupe)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page()
        pg.goto(REGISTER_URL, wait_until="networkidle", timeout=90000)
        pg.wait_for_timeout(3000)
        pg.get_by_text("View All").first.click(timeout=15000)
        pg.wait_for_timeout(5000)
        for _ in range(max_pages):
            for card in pg.query_selector_all("[class*=card]"):
                rec = _parse_card(card.inner_text())
                if rec.get("auth"):
                    records[rec["auth"]] = rec
            nxt = pg.query_selector("[aria-label='Next page']")
            if not nxt or not nxt.is_enabled():
                break
            nxt.click()
            time.sleep(delay_s)  # polite: client-side re-render + don't hammer
        browser.close()
    return list(records.values())


def _map_type(auth: str, type_str: str) -> str:
    if "/B2B/" in auth:
        return "software"
    if "/CRP/" in auth:
        return "other"
    t = (type_str or "").lower()
    if "type 1" in t:
        return "remote_casino"
    if "type 2" in t:
        return "betting"
    return "other"


def _read_col(ctx: AppContext, sheet: str, col: str) -> set[str]:
    header = SHEET_HEADERS[sheet]
    idx = header.index(col)
    rng = f"{sheet}!A2:ZZ"
    rows = ctx.sheets_client.batch_get_values([rng]).get(rng, [])
    return {row[idx].strip() for row in rows if len(row) > idx and row[idx].strip()}


def _read_operator_name_to_id(ctx: AppContext) -> dict[str, str]:
    header = SHEET_HEADERS["Operators"]
    id_idx = header.index("record_id")
    name_idx = header.index("operator_name")
    rng = "Operators!A2:ZZ"
    rows = ctx.sheets_client.batch_get_values([rng]).get(rng, [])
    out: dict[str, str] = {}
    for row in rows:
        if len(row) > max(id_idx, name_idx) and row[name_idx].strip():
            out.setdefault(row[name_idx].strip(), row[id_idx].strip())
    return out


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
    data = scrape_register()
    print(f"Scraped {len(data)} MGA licensees")

    existing_name_to_id = _read_operator_name_to_id(ctx)
    existing_lics = _read_col(ctx, "Licences", "official_licence_number")

    # Seed the map with existing operators so collisions (a company already in
    # the roster, e.g. from another jurisdiction) get their licence linked to
    # the existing operator_id rather than a blank FK.
    company_to_opid: dict[str, str] = dict(existing_name_to_id)

    seen: set[str] = set()
    new_companies = []
    company_reg: dict[str, str] = {}
    for d in data:
        name = (d.get("company") or "").strip()
        if not name:
            continue
        company_reg.setdefault(name, (d.get("reg") or "").strip())
        if name in existing_name_to_id or name in seen:
            continue
        seen.add(name)
        new_companies.append(name)

    service = RegistryService(ctx.writer)
    print(f"New operators to create: {len(new_companies)}")
    if not args.dry_run:
        for chunk in _chunks(new_companies, args.chunk):
            fields = [
                {
                    "operator_name": n,
                    "company_number": company_reg.get(n, ""),
                    "headquarters_country": "MT",
                    "source_id": args.source_id,
                }
                for n in chunk
            ]
            results = service.register_operators(
                fields, actor=ACTOR, ingestion_run_id=ctx.ingestion_run_id
            )
            for n, r in zip(chunk, results, strict=True):
                company_to_opid[n] = r.record_id

    licence_fields = []
    skipped = 0
    for d in data:
        auth = (d.get("auth") or "").strip()
        if not auth or auth in existing_lics:
            skipped += 1
            continue
        name = (d.get("company") or "").strip()
        licence_fields.append(
            {
                "operator_id": company_to_opid.get(name, ""),
                "regulator": REGULATOR,
                "jurisdiction": JURISDICTION,
                "official_licence_number": auth,
                "licence_type": _map_type(auth, d.get("type", "")),
                "licence_status": "active",
                "licensee_legal_name": name,
                "source_id": args.source_id,
                "notes": (
                    f"MGA register; company_reg={d.get('reg', '')}; "
                    f"auth_type={d.get('type', '')}; status not itemised in list view"
                ),
            }
        )

    print(f"New licences to write: {len(licence_fields)} (skipping {skipped} existing)")
    if not args.dry_run and licence_fields:
        total = 0
        for chunk in _chunks(licence_fields, args.chunk):
            total += len(
                service.register_licences(chunk, actor=ACTOR, ingestion_run_id=ctx.ingestion_run_id)
            )
        print(f"  wrote {total} licences")
    if args.dry_run:
        print("[dry-run] nothing written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
