"""Warm a cold `FingerprintStore` from the live workbook (research.md
decision #10: the cache is rebuildable from Sheets/Drive, never itself a
system of record).

Without this, a fresh checkout, a deleted `.cache/` directory, or simply
the first CLI invocation in a new environment would have an empty local
cache and could re-create rows that already exist in the workbook —
directly undermining SC-005 ("re-running ingestion against an unchanged
source produces zero duplicate facts, on every run", not just "on every
run within one warm process"). `AppContext.fingerprint_store` calls this
once, automatically, whenever the store is empty.
"""

from __future__ import annotations

from casino_intel.cache.fingerprint_store import FingerprintStore
from casino_intel.sheets.client import SheetsClient
from casino_intel.sheets.schema_definitions import SHEET_HEADERS

OBSERVATIONS_SHEET = "Observations"
DOCUMENTS_SHEET = "Documents"


def warm_cache_from_sheets(client: SheetsClient, store: FingerprintStore) -> None:
    """Rebuild `store`'s indexes from the current `Observations` and
    `Documents` sheets, but only if the store is currently empty (a cheap,
    safe no-op on an already-warm cache — avoids paying this cost on every
    single CLI invocation once the cache is populated)."""
    if not store.is_empty():
        return

    obs_range = f"{OBSERVATIONS_SHEET}!A2:ZZ"
    doc_range = f"{DOCUMENTS_SHEET}!A2:ZZ"
    values = client.batch_get_values([obs_range, doc_range])  # one API call for both

    obs_header = SHEET_HEADERS[OBSERVATIONS_SHEET]
    obs_rows = values.get(obs_range, [])
    fingerprint_col = obs_header.index("fingerprint")
    id_col = obs_header.index("record_id")
    status_col = obs_header.index("status")
    observations = [
        {"fingerprint": row[fingerprint_col], "observation_id": row[id_col]}
        for row in obs_rows
        if len(row) > fingerprint_col
        and row[fingerprint_col]
        and (len(row) <= status_col or row[status_col] != "superseded")
    ]
    store.rebuild_from_observations(observations)

    doc_header = SHEET_HEADERS[DOCUMENTS_SHEET]
    doc_rows = values.get(doc_range, [])
    doc_source_col = doc_header.index("source_id")
    doc_hash_col = doc_header.index("content_hash")
    doc_id_col = doc_header.index("record_id")
    documents = [
        {
            "source_id": row[doc_source_col],
            "content_hash": row[doc_hash_col],
            "document_id": row[doc_id_col],
        }
        for row in doc_rows
        if len(row) > doc_hash_col and row[doc_hash_col]
    ]
    store.rebuild_from_documents(documents)
