"""Operator entity (data-model.md "Entity: Operator", source doc §9.3)."""

from __future__ import annotations

from pydantic import Field

from casino_intel.models.base import Record
from casino_intel.models.vocab import OwnershipType


class Operator(Record):
    operator_name: str
    former_names: list[str] = Field(default_factory=list)
    ultimate_parent: str = ""
    ownership_type: OwnershipType = OwnershipType.UNKNOWN
    listed_exchange: str = ""
    ticker: str = ""
    headquarters_country: str = ""
    company_number: str = ""
    website: str = ""
    investor_relations_url: str = ""
    reporting_currency: str = ""
    financial_year_end: str = ""  # "MM-DD"
    employees_reported: int | None = None
    last_verified_at: str | None = None  # date, ISO string for sheet round-tripping
