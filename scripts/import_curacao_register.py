#!/usr/bin/env python3
"""Import the Curaçao Gaming Authority (CGA/LOK) online-gaming licence register
as Operators + Licences.

The CGA publishes its register as PDFs (linked from
https://www.cga.cw/en/133i348441001). This downloads the OGL (online gaming)
registry PDF and parses its table (License number, Licensee, Company type,
Company registration number, Issued, Expires, Status).

Models each entry as one Operator (licensee, with the Curaçao company reg
number, HQ=CW) + one Licence (jurisdiction=CW). No Brand rows (the register
lists no domains) — consistent with the Anjouan/MGA imports. Operators deduped
by name (so a company licensed in several jurisdictions is one operator),
licences by number; chunked, idempotent.

Run from the repo root. Requires GOOGLE_APPLICATION_CREDENTIALS + SPREADSHEET_ID
and an existing --source-id.

Usage:
    python scripts/import_curacao_register.py --source-id source_XXX [--chunk 500] [--dry-run]
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from datetime import datetime

import httpx
import pdfplumber

from casino_intel.cli.context import AppContext
from casino_intel.services.registry_service import RegistryService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

ACTOR = "import_curacao_register"
REGISTER_PAGE = "https://www.cga.cw/en/133i348441001"
OGL_PDF = "https://gamingcontrol.spin-cdn.com/media/license_registry/20260722_20260722_ogl_license_registry.pdf"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/126 Safari/537.36"
    )
}
REGULATOR = "Curaçao Gaming Authority"
JURISDICTION = "CW"

# "145. OGL/ 2024/894/1037 Codex B.V. B2C 160873 January 14, 2026 July 14, 2026 [status]"
_LINE = re.compile(
    r"^\s*\d+\.\s+"
    r"((?:CGA|OGL)/\s*\d{4}/\d+/\d+)\s+"
    r"(.+?)\s+"
    r"(B2B\s*&\s*B2C|B2C\s*&\s*B2B|B2B|B2C)\s+"
    r"(\d{4,})\s+"
    r"([A-Z][a-z]+ \d{1,2}, \d{4})\s+"
    r"(N/A|[A-Z][a-z]+ \d{1,2}, \d{4})"
    r"(.*)$"
)
_STATUS_MAP = {
    "": "active",
    "indefinite": "active",
    "expired": "surrendered",
    "assessment in progress": "unknown",
}


def _iso(value: str) -> str | None:
    v = (value or "").strip()
    if not v or v == "N/A":
        return None
    try:
        return datetime.strptime(v, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def _parse_pdf(content: bytes) -> list[dict]:
    recs: dict[str, dict] = {}
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for pg in pdf.pages:
            for ln in (pg.extract_text() or "").split("\n"):
                m = _LINE.match(ln)
                if not m:
                    continue
                lic = re.sub(r"\s+", "", m.group(1))
                raw_status = m.group(7).strip()
                recs[lic] = {
                    "license": lic,
                    "licensee": m.group(2).strip().replace("\n", " "),
                    "type": m.group(3).replace(" ", ""),
                    "reg": m.group(4),
                    "issued": _iso(m.group(5)),
                    "expires": _iso(m.group(6)),
                    "raw_status": raw_status,
                    "status": _STATUS_MAP.get(raw_status.lower(), "unknown"),
                }
    return list(recs.values())


def _read_operator_name_to_id(ctx: AppContext) -> dict[str, str]:
    header = SHEET_HEADERS["Operators"]
    id_idx, name_idx = header.index("record_id"), header.index("operator_name")
    rows = ctx.sheets_client.batch_get_values(["Operators!A2:ZZ"]).get("Operators!A2:ZZ", [])
    out: dict[str, str] = {}
    for row in rows:
        if len(row) > max(id_idx, name_idx) and row[name_idx].strip():
            out.setdefault(row[name_idx].strip(), row[id_idx].strip())
    return out


def _read_licence_numbers(ctx: AppContext) -> set[str]:
    header = SHEET_HEADERS["Licences"]
    idx = header.index("official_licence_number")
    rows = ctx.sheets_client.batch_get_values(["Licences!A2:ZZ"]).get("Licences!A2:ZZ", [])
    return {row[idx].strip() for row in rows if len(row) > idx and row[idx].strip()}


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
    content = httpx.get(OGL_PDF, headers=UA, follow_redirects=True, timeout=120).content
    data = _parse_pdf(content)
    print(f"Parsed {len(data)} CGA/OGL licences")

    name_to_opid = _read_operator_name_to_id(ctx)
    company_to_opid: dict[str, str] = dict(name_to_opid)
    existing_lics = _read_licence_numbers(ctx)

    seen: set[str] = set()
    new_companies = []
    company_reg: dict[str, str] = {}
    for d in data:
        name = d["licensee"].strip()
        if not name:
            continue
        company_reg.setdefault(name, d["reg"])
        if name in name_to_opid or name in seen:
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
                    "headquarters_country": "CW",
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
        num = d["license"]
        if not num or num in existing_lics:
            skipped += 1
            continue
        licence_fields.append(
            {
                "operator_id": company_to_opid.get(d["licensee"].strip(), ""),
                "regulator": REGULATOR,
                "jurisdiction": JURISDICTION,
                "official_licence_number": num,
                "licence_type": "software" if d["type"] == "B2B" else "other",
                "licence_status": d["status"],
                "effective_date": d["issued"],
                "expiry_date": d["expires"],
                "licensee_legal_name": d["licensee"].strip(),
                "source_id": args.source_id,
                "notes": (
                    f"CGA LOK register; company_type={d['type']}; "
                    f"company_reg={d['reg']}; register_status={d['raw_status'] or 'active'}"
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
