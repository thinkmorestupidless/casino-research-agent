"""Local, rebuildable SQLite index of observation fingerprints and document
content hashes (research.md decision #10).

This is a *cache*, never a system of record: everything in it can be
reconstructed from the Google Sheets workbook and Drive archive via
:meth:`FingerprintStore.rebuild_from_observations`. It exists purely so
idempotency/dedup checks (contracts/observation-write-contract.md §2) don't
require re-reading the full ``Observations`` sheet on every ingestion run.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable
from pathlib import Path

DEFAULT_CACHE_PATH = ".cache/casino_intel.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS observation_fingerprints (
    fingerprint TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_hashes (
    source_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    document_id TEXT NOT NULL,
    PRIMARY KEY (source_id, content_hash)
);
"""


class FingerprintStore:
    """SQLite-backed fingerprint/document-hash index."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.environ.get("CASINO_INTEL_CACHE_PATH") or DEFAULT_CACHE_PATH
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> FingerprintStore:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # --- observation fingerprints -------------------------------------------------

    def has_fingerprint(self, fingerprint: str) -> str | None:
        """Return the existing observation_id for this fingerprint, or None."""
        row = self._conn.execute(
            "SELECT observation_id FROM observation_fingerprints WHERE fingerprint = ?",
            (fingerprint,),
        ).fetchone()
        return row[0] if row else None

    def record_fingerprint(self, fingerprint: str, observation_id: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO observation_fingerprints (fingerprint, observation_id) "
            "VALUES (?, ?)",
            (fingerprint, observation_id),
        )
        self._conn.commit()

    def rebuild_from_observations(self, observations: Iterable[dict]) -> int:
        """Rebuild the fingerprint index from scratch given active observation rows.

        Each item must have ``fingerprint`` and ``observation_id`` keys
        (typically produced by re-reading the ``Observations`` sheet and
        recomputing fingerprints for all ``active`` rows).
        """
        self._conn.execute("DELETE FROM observation_fingerprints")
        count = 0
        for obs in observations:
            self._conn.execute(
                "INSERT OR REPLACE INTO observation_fingerprints (fingerprint, observation_id) "
                "VALUES (?, ?)",
                (obs["fingerprint"], obs["observation_id"]),
            )
            count += 1
        self._conn.commit()
        return count

    # --- document content hashes ---------------------------------------------------

    def has_document_hash(self, source_id: str, content_hash: str) -> str | None:
        """Return the existing document_id for this (source_id, content_hash), or None."""
        row = self._conn.execute(
            "SELECT document_id FROM document_hashes WHERE source_id = ? AND content_hash = ?",
            (source_id, content_hash),
        ).fetchone()
        return row[0] if row else None

    def record_document_hash(self, source_id: str, content_hash: str, document_id: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO document_hashes (source_id, content_hash, document_id) "
            "VALUES (?, ?, ?)",
            (source_id, content_hash, document_id),
        )
        self._conn.commit()

    def rebuild_from_documents(self, documents: Iterable[dict]) -> int:
        """Rebuild the document-hash index from scratch. Each item must have
        ``source_id``, ``content_hash`` and ``document_id`` keys."""
        self._conn.execute("DELETE FROM document_hashes")
        count = 0
        for doc in documents:
            self._conn.execute(
                "INSERT OR REPLACE INTO document_hashes (source_id, content_hash, document_id) "
                "VALUES (?, ?, ?)",
                (doc["source_id"], doc["content_hash"], doc["document_id"]),
            )
            count += 1
        self._conn.commit()
        return count

    def is_empty(self) -> bool:
        """True if neither index has any entries — the signal a fresh/cold
        cache (new machine, deleted `.cache/`, or a fresh `:memory:`
        connection) should be warmed from the Sheets workbook before being
        trusted for dedup decisions (see `services/cache_warmup.py`)."""
        obs_count = self._conn.execute("SELECT COUNT(*) FROM observation_fingerprints").fetchone()[
            0
        ]
        doc_count = self._conn.execute("SELECT COUNT(*) FROM document_hashes").fetchone()[0]
        return obs_count == 0 and doc_count == 0

    def latest_document_hash(self, source_id: str) -> str | None:
        """Return the most recently recorded content hash for a source, if any."""
        row = self._conn.execute(
            "SELECT content_hash FROM document_hashes WHERE source_id = ? "
            "ORDER BY ROWID DESC LIMIT 1",
            (source_id,),
        ).fetchone()
        return row[0] if row else None
