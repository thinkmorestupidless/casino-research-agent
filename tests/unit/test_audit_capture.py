"""Playwright-assisted capture flow tests (T078).

No real browser is ever launched here — `browser_factory` is monkeypatched
with an in-memory fake, since Playwright's browser binaries are not
installed in this environment (only the `playwright` Python package is).
"""

from __future__ import annotations

from casino_intel.fetching.audit_capture import capture_permitted_pages
from casino_intel.services.journey_safety import PERMITTED_CAPTURE_STAGES, RESTRICTED_ACTIONS


class _FakePage:
    def __init__(self) -> None:
        self.urls_visited: list[str] = []

    def goto(self, url: str) -> None:
        self.urls_visited.append(url)

    def screenshot(self) -> bytes:
        return b"fake-screenshot-bytes"


class _FakeBrowser:
    def __init__(self) -> None:
        self.page = _FakePage()
        self.closed = False

    def new_page(self) -> _FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True


class _FakeSession:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _FakeDrive:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str]] = []

    def upload(self, relative_folder, filename, content, mime_type):
        self.uploads.append((relative_folder, filename))
        return (f"file_{filename}", f"{relative_folder}/{filename}", "deadbeef")


def _factory(browser, session):
    def factory():
        return session, browser

    return factory


def test_captures_every_permitted_stage_by_default():
    browser, session, drive = _FakeBrowser(), _FakeSession(), _FakeDrive()
    results = capture_permitted_pages(
        "https://example-casino.example",
        drive,
        brand_id="brand_1",
        audit_date="2026-07-24",
        browser_factory=_factory(browser, session),
    )
    assert [r.stage for r in results] == list(PERMITTED_CAPTURE_STAGES)


def test_archives_each_screenshot_via_drive_under_the_expected_folder():
    browser, session, drive = _FakeBrowser(), _FakeSession(), _FakeDrive()
    capture_permitted_pages(
        "https://example-casino.example",
        drive,
        brand_id="brand_1",
        audit_date="2026-07-24",
        browser_factory=_factory(browser, session),
    )
    assert all(folder == "screenshots/brand/2026-07-24" for folder, _ in drive.uploads)
    assert len(drive.uploads) == len(PERMITTED_CAPTURE_STAGES)


def test_browser_and_session_are_torn_down():
    browser, session, drive = _FakeBrowser(), _FakeSession(), _FakeDrive()
    capture_permitted_pages(
        "https://example-casino.example",
        drive,
        brand_id="brand_1",
        audit_date="2026-07-24",
        browser_factory=_factory(browser, session),
    )
    assert browser.closed and session.stopped


def test_never_visits_a_restricted_stage_even_if_requested():
    browser, session, drive = _FakeBrowser(), _FakeSession(), _FakeDrive()
    requested = ["homepage", "depositing_funds", "placing_a_wager", "lobby"]
    results = capture_permitted_pages(
        "https://example-casino.example",
        drive,
        brand_id="brand_1",
        audit_date="2026-07-24",
        stages=requested,
        browser_factory=_factory(browser, session),
    )
    visited_stages = {r.stage for r in results}
    assert not (visited_stages & RESTRICTED_ACTIONS)
    # The journey stopped at the first restricted stage — "lobby" (which
    # came after it in the requested list) is never reached either.
    assert visited_stages == {"homepage"}
