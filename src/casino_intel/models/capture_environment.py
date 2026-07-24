"""Standard audit capture-environment metadata (source doc §13.1, spec FR-031).

Every UX/brand audit is expected to be conducted under a fixed, comparable
environment: a defined geography, viewport/device, logged-in/cookie state,
and a recorded date/time. This module is the single reusable definition of
that environment so `UXAudit`, `BrandAudit`, and the capture flow
(`fetching/audit_capture.py`) all describe it identically.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DeviceType(StrEnum):
    """Mirrors `config/vocabularies.yaml` `device_types`."""

    DESKTOP = "desktop"
    MOBILE_WEB = "mobile_web"
    IOS_APP = "ios_app"
    ANDROID_APP = "android_app"


class CookieState(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFAULT = "default"


class VisitorState(StrEnum):
    NEW = "new"
    RETURNING = "returning"


class CaptureEnvironment(BaseModel):
    """The fixed conditions an audit was captured under (source doc §13.1)."""

    geography: str = "GB"
    language: str = "en"
    device_type: DeviceType = DeviceType.DESKTOP
    viewport: str = ""
    browser: str = ""
    logged_in_state: bool = False
    new_or_returning_visitor: VisitorState = VisitorState.NEW
    cookie_state: CookieState = CookieState.ACCEPTED
    network_profile: str = ""
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def audit_date(self) -> date:
        return self.captured_at.date()
