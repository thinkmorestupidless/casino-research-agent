"""Observation idempotency fingerprint (source doc §11.4, research.md decision #15).

``fingerprint()`` hashes exactly the fields the source requirements document
specifies — adopted verbatim, not reinvented (research.md decision #15).
"""

from __future__ import annotations

import hashlib
from datetime import date

_FIELDS = (
    "subject_id",
    "metric_id",
    "period_start",
    "period_end",
    "as_of_date",
    "geography",
    "segment",
    "source_id",
    "raw_value",
)


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def fingerprint(observation: dict[str, object]) -> str:
    """Compute the SHA-256 fingerprint for an observation-like mapping.

    ``observation`` must contain (or omit, treated as empty) each of
    ``_FIELDS``. Any other keys are ignored — this keeps the fingerprint
    stable even as the Observation schema grows.
    """
    parts = [_stringify(observation.get(field)) for field in _FIELDS]
    digest_input = "|".join(parts).encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()
