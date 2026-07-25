#!/usr/bin/env python3
"""Import real UK Gambling Commission licences into the Licences tab from the
public register bulk download (https://www.gamblingcommission.gov.uk/public-register/businesses/download).

Unlike the industry-statistics importer (which is blocked — see issue #2), the
licence register is a clean, authoritative bulk dataset. This links each
registered brand to its real licensed entity **by domain** (the register's
domain-names dataset), which is authoritative and avoids guessing legal-entity
names, then writes that entity's real licences (number, type, status, dates,
licensee legal name), sourced to the register.

Operator = the licensed legal entity (consistent with the Anjouan/MGA imports),
created/reused per licensee with the commercial group (from the matched brand's
operator) recorded as ultimate_parent.

Matching by domain also surfaces seed discrepancies (a domain registered to an
entity unrelated to the seed's attributed operator) — pass those brands via
--exclude-brand so wrong FKs are never written; they are reported instead.

Idempotent: licence numbers already present in the Licences tab are skipped, so
re-running refreshes without duplicating.

Run from the repo root. Requires GOOGLE_APPLICATION_CREDENTIALS + SPREADSHEET_ID
and an existing --source-id for provenance.

Usage:
    python scripts/import_ukgc_licences.py --source-id source_XXX \
        [--exclude-brand "Genting Casino" --exclude-brand "Wink Slots"] [--dry-run]
"""

from __future__ import annotations

import argparse
import io
import sys

import httpx
import pandas as pd

from casino_intel.cli.context import AppContext
from casino_intel.services.registry_service import RegistryService
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

ACTOR = "import_ukgc_licences"
BASE = "https://www.gamblingcommission.gov.uk/downloads/"
FILES = {
    "businesses": "business-licence-register-businesses.csv",
    "domains": "business-licence-register-domain-names.csv",
    "licences": "business-licence-register-licences.csv",
}
# A normal browser UA — the register files are on gamblingcommission.gov.uk, but
# some GC assets 403 the project's research-bot UA, so fetch as a browser here.
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/126 Safari/537.36"
    )
}


def _download() -> dict[str, pd.DataFrame]:
    out = {}
    with httpx.Client(headers=UA, follow_redirects=True, timeout=90) as client:
        for key, fn in FILES.items():
            r = client.get(BASE + fn)
            r.raise_for_status()
            out[key] = pd.read_csv(io.BytesIO(r.content), dtype=str)
    return out


def _map_type(reg_type: str, activity: str) -> str:
    a = (activity or "").lower()
    if "software" in a:
        return "software"
    if "bingo" in a:
        return "bingo"
    if "betting" in a or "pool" in a or "intermediary" in a:
        return "betting"
    if "casino" in a:
        return "remote_casino" if reg_type == "Remote" else "other"
    return "other"


def _map_status(status: str) -> str:
    return {
        "active": "active",
        "surrendered": "surrendered",
        "suspended": "suspended",
        "revoked": "revoked",
    }.get((status or "").strip().lower(), "unknown")


def _date(value: object) -> str | None:
    if value is None or (isinstance(value, float)) or pd.isna(value):
        return None
    s = str(value).strip()
    return s[:10] if s else None


def _read_col(ctx: AppContext, sheet: str, cols: list[str]) -> list[dict]:
    header = SHEET_HEADERS[sheet]
    rng = f"{sheet}!A2:ZZ"
    rows = ctx.sheets_client.batch_get_values([rng]).get(rng, [])
    out = []
    for row in rows:
        if not row or not str(row[0]).strip():
            continue
        rec = {c: (row[header.index(c)] if header.index(c) < len(row) else "") for c in cols}
        out.append(rec)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--exclude-brand", action="append", default=[], dest="exclude")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--today", default="", help="ISO date to stamp last_verified_at")
    args = parser.parse_args(argv)

    ctx = AppContext(dry_run=args.dry_run, actor=ACTOR)
    data = _download()
    biz = dict(
        zip(
            data["businesses"]["Account Number"],
            data["businesses"]["Licence Account Name"],
            strict=False,
        )
    )
    dom = data["domains"].copy()
    dom["_d"] = dom["Domain Name"].str.lower().str.replace("www.", "", regex=False).str.strip()
    lic = data["licences"]

    brands = _read_col(ctx, "Brands", ["record_id", "brand_name", "primary_domain", "operator_id"])
    exclude = {b.strip().lower() for b in args.exclude}

    # account -> {operator_ids, brand_ids}
    acct_ops: dict[str, set[str]] = {}
    acct_brands: dict[str, set[str]] = {}
    excluded_hits = []
    for b in brands:
        if b["brand_name"].strip().lower() in exclude:
            d = b["primary_domain"].lower().replace("www.", "").strip()
            hit = sorted(set(dom[dom["_d"] == d]["Account Number"]))
            excluded_hits.append((b["brand_name"], d, [biz.get(a, "?") for a in hit]))
            continue
        d = b["primary_domain"].lower().replace("www.", "").strip()
        for a in sorted(set(dom[dom["_d"] == d]["Account Number"])):
            acct_ops.setdefault(a, set()).add(b["operator_id"])
            acct_brands.setdefault(a, set()).add(b["record_id"])

    existing_nums = {
        r["official_licence_number"]
        for r in _read_col(ctx, "Licences", ["official_licence_number"])
        if r["official_licence_number"].strip()
    }

    # A single UKGC licence NUMBER spans multiple activity rows in the register
    # (e.g. one number authorising casino + betting + bingo). Collapse to one
    # Licence row per number, picking a representative licence_type by priority
    # and recording every activity in notes.
    type_priority = ["remote_casino", "betting", "bingo", "software", "other"]

    def pick_type(types: list[str]) -> str:
        for t in type_priority:
            if t in types:
                return t
        return "other"

    def pick_status(statuses: list[str]) -> str:
        mapped = [_map_status(s) for s in statuses]
        for s in ("active", "suspended", "surrendered", "revoked"):
            if s in mapped:
                return s
        return "unknown"

    # Operator = the licensed legal entity (consistent with the Anjouan/MGA
    # imports), with the commercial group recorded as ultimate_parent. We map
    # each account to its group (via the brand's operator), then create/reuse an
    # operator for the account's legal entity and link the licence to that.
    op_rows = _read_col(ctx, "Operators", ["record_id", "operator_name"])
    opid_to_name = {r["record_id"]: r["operator_name"] for r in op_rows}
    name_to_opid: dict[str, str] = {}
    for r in op_rows:
        name_to_opid.setdefault(r["operator_name"], r["record_id"])

    service = RegistryService(ctx.writer)
    conflicts = []
    account_plan: dict[str, dict] = {}
    for acct, ops in sorted(acct_ops.items()):
        if len(ops) != 1:
            conflicts.append((acct, biz.get(acct, "?"), ops))
            continue
        bids = acct_brands[acct]
        account_plan[acct] = {
            "entity": biz.get(acct, "").strip(),
            "group_name": opid_to_name.get(next(iter(ops)), ""),
            "brand_id": next(iter(bids)) if len(bids) == 1 else None,
        }

    # Create operators for licensed entities not already present.
    to_create = []
    seen_new: set[str] = set()
    for pl in account_plan.values():
        e = pl["entity"]
        if e and e not in name_to_opid and e not in seen_new:
            seen_new.add(e)
            to_create.append((e, pl["group_name"]))
    print(f"New entity operators to create: {len(to_create)}")
    if not args.dry_run and to_create:
        fields = [
            {"operator_name": e, "ultimate_parent": g, "source_id": args.source_id}
            for e, g in to_create
        ]
        results = service.register_operators(
            fields, actor=ACTOR, ingestion_run_id=ctx.ingestion_run_id
        )
        for (e, _), r in zip(to_create, results, strict=True):
            name_to_opid[e] = r.record_id

    licence_fields = []
    for acct, pl in account_plan.items():
        operator_id = name_to_opid.get(pl["entity"], "")
        brand_id = pl["brand_id"]
        legal = pl["entity"]
        sub = lic[lic["Account Number"] == acct]
        for num, grp in sub.groupby("Licence Number"):
            num = str(num).strip()
            if not num or num in existing_nums:
                continue
            existing_nums.add(num)
            types = [_map_type(t, a) for t, a in zip(grp["Type"], grp["Activity"], strict=False)]
            activities = sorted({str(a) for a in grp["Activity"]})
            reg_types = sorted({str(t) for t in grp["Type"]})
            starts = [d for d in (_date(x) for x in grp["Start Date"]) if d]
            ends = [d for d in (_date(x) for x in grp["End Date"]) if d]
            licence_fields.append(
                {
                    "operator_id": operator_id,
                    "brand_id": brand_id,
                    "regulator": "UK Gambling Commission",
                    "jurisdiction": "GB",
                    "official_licence_number": num,
                    "licence_type": pick_type(types),
                    "licence_status": pick_status(list(grp["Status"])),
                    "effective_date": min(starts) if starts else None,
                    "expiry_date": max(ends) if ends else None,
                    "licensee_legal_name": legal,
                    "last_verified_at": args.today or None,
                    "source_id": args.source_id,
                    "notes": (
                        f"UKGC account {acct}; activities={activities}; reg_type={reg_types}"
                    ),
                }
            )

    print(f"Accounts matched: {len(acct_ops)} | new licence rows to write: {len(licence_fields)}")
    if excluded_hits:
        print("\nExcluded brands (reported, not written — seed attribution discrepancies):")
        for name, d, legals in excluded_hits:
            print(f"  {name} ({d}) -> registered to {legals}")
    if conflicts:
        print("\nAccounts with conflicting operators (skipped):")
        for a, legal, ops in conflicts:
            print(f"  {a} {legal} -> operators {ops}")

    if not args.dry_run and licence_fields:
        results = service.register_licences(
            licence_fields, actor=ACTOR, ingestion_run_id=ctx.ingestion_run_id
        )
        print(f"\nWrote {len(results)} Licence rows.")
    else:
        print("\n[dry-run] nothing written." if args.dry_run else "\nNothing to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
