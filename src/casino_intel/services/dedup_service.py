"""Idempotent dedup check against the fingerprint cache, prior to any
append (contracts/observation-write-contract.md §2).

`sheets.writer.SheetsWriter.append_observation` already performs this check
inline at write time; this service exposes the same check standalone so
callers earlier in the pipeline (e.g. the ingestion orchestrator) can skip
redundant normalisation/validation work for a fact that will turn out to be
a duplicate, without duplicating fingerprint logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from casino_intel.cache.fingerprint_store import FingerprintStore
from casino_intel.validation.fingerprint import fingerprint as compute_fingerprint


@dataclass(frozen=True)
class DedupCheck:
    fingerprint: str
    is_duplicate: bool
    existing_observation_id: str | None


class DedupService:
    def __init__(self, fingerprint_store: FingerprintStore) -> None:
        self.fingerprint_store = fingerprint_store

    def check(self, observation_like: dict[str, object]) -> DedupCheck:
        """`observation_like` must carry (or omit, treated as empty) the
        fields `validation.fingerprint.fingerprint()` hashes on."""
        fp = compute_fingerprint(observation_like)
        existing_id = self.fingerprint_store.has_fingerprint(fp)
        return DedupCheck(
            fingerprint=fp,
            is_duplicate=existing_id is not None,
            existing_observation_id=existing_id,
        )
