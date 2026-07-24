"""Unit tests for the generic HTTP fetcher's access-policy enforcement
(spec FR-013): paywalled/auth-required sources are refused before any
network call, and robots.txt is consulted and respected. No live network
access — httpx is driven entirely through `httpx.MockTransport`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from casino_intel.fetching.fetcher import DomainRateLimiter, Fetcher, RobotsDisallowedError
from casino_intel.models.source import AccessDeniedError, Source

NOW = datetime.now(UTC)


def _source(**overrides) -> Source:
    defaults = dict(
        record_id="source_1",
        created_at=NOW,
        created_by="tester",
        updated_at=NOW,
        source_type="regulator_statistics",
        url="https://example.gov/statistics",
    )
    defaults.update(overrides)
    return Source(**defaults)


def _no_rate_limit_fetcher(transport: httpx.MockTransport, **kwargs) -> Fetcher:
    client = httpx.Client(transport=transport)
    return Fetcher(client=client, rate_limiter=DomainRateLimiter(min_interval_seconds=0), **kwargs)


def test_fetch_refuses_paywalled_source_without_any_network_call() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, text="should never be reached")

    fetcher = _no_rate_limit_fetcher(httpx.MockTransport(handler))
    source = _source(paywalled=True)

    with pytest.raises(AccessDeniedError):
        fetcher.fetch(source)
    assert calls == []


def test_fetch_refuses_authentication_required_source() -> None:
    fetcher = _no_rate_limit_fetcher(httpx.MockTransport(lambda r: httpx.Response(200)))
    source = _source(authentication_required=True)

    with pytest.raises(AccessDeniedError):
        fetcher.fetch(source)


def test_fetch_respects_robots_disallow() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /statistics")
        return httpx.Response(200, text="page content")

    fetcher = _no_rate_limit_fetcher(httpx.MockTransport(handler))
    source = _source()

    with pytest.raises(RobotsDisallowedError):
        fetcher.fetch(source)


def test_fetch_succeeds_when_robots_allows() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(
            200, content=b"<html>ok</html>", headers={"content-type": "text/html"}
        )

    fetcher = _no_rate_limit_fetcher(httpx.MockTransport(handler))
    source = _source()

    result = fetcher.fetch(source)
    assert result.status_code == 200
    assert result.content == b"<html>ok</html>"
    assert result.content_type == "text/html"


def test_fetch_permissive_when_robots_txt_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, content=b"content")

    fetcher = _no_rate_limit_fetcher(httpx.MockTransport(handler))
    result = fetcher.fetch(_source())
    assert result.content == b"content"


def test_fetch_raises_fetch_error_after_retry_budget_exhausted() -> None:
    from casino_intel.fetching.fetcher import FetchError

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(503)

    fetcher = _no_rate_limit_fetcher(httpx.MockTransport(handler))
    with pytest.raises(FetchError):
        fetcher.fetch(_source())
