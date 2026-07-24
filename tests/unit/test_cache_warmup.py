"""Cold-cache warmup (spec SC-005): idempotency must hold even when the
local fingerprint cache is empty (fresh checkout, deleted `.cache/`, or a
new environment) — not just within one long-lived process."""

from __future__ import annotations

from casino_intel.cache.fingerprint_store import FingerprintStore
from casino_intel.services.cache_warmup import warm_cache_from_sheets
from casino_intel.sheets.schema_definitions import SHEET_HEADERS


def test_warm_cache_from_sheets_rebuilds_observation_fingerprints(sheets_client, fake_service):
    fake_service.add_sheet("Observations", SHEET_HEADERS["Observations"])
    fake_service.add_sheet("Documents", SHEET_HEADERS["Documents"])
    header = SHEET_HEADERS["Observations"]
    row = ["" for _ in header]
    row[header.index("record_id")] = "obs_existing"
    row[header.index("fingerprint")] = "abc123"
    row[header.index("status")] = "active"
    fake_service.sheets["Observations"].append(row)

    store = FingerprintStore(path=":memory:")
    warm_cache_from_sheets(sheets_client, store)

    assert store.has_fingerprint("abc123") == "obs_existing"


def test_warm_cache_from_sheets_rebuilds_document_hashes(sheets_client, fake_service):
    fake_service.add_sheet("Observations", SHEET_HEADERS["Observations"])
    fake_service.add_sheet("Documents", SHEET_HEADERS["Documents"])
    header = SHEET_HEADERS["Documents"]
    row = ["" for _ in header]
    row[header.index("record_id")] = "document_existing"
    row[header.index("source_id")] = "source_1"
    row[header.index("content_hash")] = "hash-xyz"
    fake_service.sheets["Documents"].append(row)

    store = FingerprintStore(path=":memory:")
    warm_cache_from_sheets(sheets_client, store)

    assert store.has_document_hash("source_1", "hash-xyz") == "document_existing"


def test_warm_cache_is_a_noop_on_an_already_warm_cache(sheets_client, fake_service):
    fake_service.add_sheet("Observations", SHEET_HEADERS["Observations"])
    fake_service.add_sheet("Documents", SHEET_HEADERS["Documents"])
    store = FingerprintStore(path=":memory:")
    store.record_fingerprint("already-there", "obs_1")

    # Even though the sheet now has different data, a non-empty cache is
    # trusted as-is (this is a startup warmup, not a per-call sync).
    header = SHEET_HEADERS["Observations"]
    row = ["" for _ in header]
    row[header.index("fingerprint")] = "should-not-be-loaded"
    row[header.index("record_id")] = "obs_2"
    fake_service.sheets["Observations"].append(row)

    warm_cache_from_sheets(sheets_client, store)

    assert store.has_fingerprint("already-there") == "obs_1"
    assert store.has_fingerprint("should-not-be-loaded") is None


def test_warm_cache_handles_missing_sheets_gracefully(sheets_client):
    """A brand-new, not-yet-initialised workbook has no Observations/Documents
    tabs at all — warming must not raise; an empty cache is correct there."""
    store = FingerprintStore(path=":memory:")
    warm_cache_from_sheets(sheets_client, store)  # should not raise
    assert store.is_empty()
