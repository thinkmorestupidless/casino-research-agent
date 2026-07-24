"""Brand entity (data-model.md "Entity: Brand", source doc §9.2)."""

from __future__ import annotations

from pydantic import Field, field_validator

from casino_intel.models.base import Record
from casino_intel.models.vocab import BrandStatus, BrandType


class Brand(Record):
    brand_name: str
    legal_or_trading_name: str = ""
    operator_id: str
    primary_domain: str
    alternate_domains: list[str] = Field(default_factory=list)
    launch_date: str | None = None
    brand_status: BrandStatus = BrandStatus.ACTIVE
    brand_type: BrandType
    primary_market: str = ""  # ISO 3166-1 alpha-2
    active_markets: list[str] = Field(default_factory=list)
    restricted_markets: list[str] = Field(default_factory=list)
    primary_language: str = ""
    currency_options: list[str] = Field(default_factory=list)
    mobile_web: bool = False
    native_ios_app: bool = False
    native_android_app: bool = False
    crypto_supported: bool = False
    public_description: str = ""
    research_priority: int = 3
    first_observed_at: str | None = None
    last_verified_at: str | None = None
    sampling_rationale: str = ""

    # optional fields (source doc §9.2 "Optional")
    previous_names: list[str] = Field(default_factory=list)
    slogan: str = ""
    social_handles: list[str] = Field(default_factory=list)
    affiliate_programme_name: str = ""
    customer_support_channels: list[str] = Field(default_factory=list)

    @field_validator("research_priority")
    @classmethod
    def _priority_in_range(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("research_priority must be between 1 and 5")
        return v
