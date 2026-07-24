"""Licence entity (data-model.md "Entity: Licence", source doc §9.4)."""

from __future__ import annotations

from casino_intel.models.base import Record
from casino_intel.models.vocab import LicenceStatus, LicenceType


class Licence(Record):
    operator_id: str
    brand_id: str | None = None
    regulator: str
    jurisdiction: str  # ISO alpha-2 / territory
    official_licence_number: str = ""
    licence_type: LicenceType = LicenceType.OTHER
    licence_status: LicenceStatus = LicenceStatus.UNKNOWN
    effective_date: str | None = None
    expiry_date: str | None = None
    licensee_legal_name: str = ""
    last_verified_at: str | None = None
