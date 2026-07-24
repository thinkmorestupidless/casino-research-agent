"""Playwright-based capture of permitted dynamic audit pages (T078).

Only the stages in `journey_safety.PERMITTED_CAPTURE_STAGES` (homepage,
lobby, promotions, registration-up-to-the-stop-point, footer/licence,
responsible-gambling) are ever visited — `journey_safety.stop_before_restricted`
is applied to whatever stage list is requested, so a caller cannot make this
module visit a restricted stage even by mistake (FR-033/FR-046).

The real Playwright browser launch is isolated behind `_launch_browser`, the
one function in this module that imports `playwright.sync_api` and starts a
browser process. Playwright's Python *package* is a project dependency and
safe to import, but its browser *binaries* are a separate `playwright
install` step that is not guaranteed to be present in every environment
(including this build's sandbox) — so no test may call `_launch_browser`
directly; tests inject a fake via the `browser_factory` parameter instead.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from casino_intel.drive.client import DriveClient
from casino_intel.services.journey_safety import PERMITTED_CAPTURE_STAGES, stop_before_restricted

#: Stage -> relative URL path appended to the brand's homepage URL.
STAGE_URL_PATHS: dict[str, str] = {
    "homepage": "",
    "lobby": "/casino",
    "promotions": "/promotions",
    "registration_up_to_stop_point": "/register",
    "footer_licence": "",
    "responsible_gambling": "/responsible-gambling",
}


class CapturePage(Protocol):
    """The minimal Playwright `Page` surface this module depends on."""

    def goto(self, url: str) -> Any: ...

    def screenshot(self) -> bytes: ...


class CaptureBrowser(Protocol):
    """The minimal Playwright `Browser` surface this module depends on."""

    def new_page(self) -> CapturePage: ...

    def close(self) -> None: ...


class BrowserSession(Protocol):
    """Whatever handle `browser_factory` returns alongside the browser, so
    it can be cleanly torn down (e.g. Playwright's own context manager)."""

    def stop(self) -> None: ...


@dataclass(frozen=True)
class CapturedScreenshot:
    stage: str
    file_id: str
    archive_path: str
    content_hash: str


def _launch_browser(*, headless: bool = True) -> tuple[BrowserSession, CaptureBrowser]:
    """The only place this module touches a real browser. Not covered by
    any test — see module docstring."""
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    session = sync_playwright().start()
    browser = session.chromium.launch(headless=headless)
    return session, browser


def capture_permitted_pages(
    homepage_url: str,
    drive_client: DriveClient,
    *,
    brand_id: str,
    audit_date: str,
    stages: Sequence[str] | None = None,
    browser_factory: Callable[[], tuple[BrowserSession, CaptureBrowser]] = _launch_browser,
) -> list[CapturedScreenshot]:
    """Visit each permitted capture stage in turn, screenshot it, and
    archive the screenshot via Drive at `screenshots/brand/<audit_date>/`.

    Stops before any restricted stage (FR-033/FR-046): the stages actually
    visited are `journey_safety.stop_before_restricted(stages)`, so even a
    caller-supplied `stages` list containing a restricted action never
    reaches the browser.
    """
    requested = list(stages) if stages is not None else list(PERMITTED_CAPTURE_STAGES)
    safe_stages = stop_before_restricted(requested)

    session, browser = browser_factory()
    results: list[CapturedScreenshot] = []
    try:
        page = browser.new_page()
        for stage in safe_stages:
            path = STAGE_URL_PATHS.get(stage, "")
            url = f"{homepage_url.rstrip('/')}{path}"
            page.goto(url)
            content = page.screenshot()
            filename = f"{brand_id}_{stage}.png"
            file_id, archive_path, content_hash = drive_client.upload(
                f"screenshots/brand/{audit_date}", filename, content, "image/png"
            )
            results.append(CapturedScreenshot(stage, file_id, archive_path, content_hash))
    finally:
        browser.close()
        session.stop()
    return results
