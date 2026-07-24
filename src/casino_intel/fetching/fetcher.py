"""Generic HTTP fetcher (spec FR-013, source doc §11.2, docs/source-policy.md).

Every automated fetch goes through this module so the access-control rules
are enforced in exactly one place:

- Hard refusal of paywalled/authentication-required sources
  (`Source.assert_fetchable()`), never left to the caller to remember.
- robots.txt is consulted and respected before every fetch.
- A per-domain minimum-interval rate limiter avoids hammering any one host.
- Transient failures are retried with exponential backoff (`tenacity`); the
  retry budget is bounded and a hard failure is raised rather than an
  indefinite retry loop.

No test in this codebase may perform a live network call against this
module — tests inject an `httpx.Client` built on `httpx.MockTransport`.
"""

from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from casino_intel.models.source import Source

USER_AGENT = "casino-intel-research-bot/0.1 (+https://casino-intel.internal/bot)"
DEFAULT_MIN_INTERVAL_SECONDS = 2.0
DEFAULT_TIMEOUT_SECONDS = 30.0


class RobotsDisallowedError(PermissionError):
    """Raised when robots.txt disallows fetching this URL for our agent."""


class FetchError(RuntimeError):
    """Raised once the retry budget is exhausted on a network/HTTP failure."""


@dataclass(frozen=True)
class FetchResult:
    url: str
    status_code: int
    content: bytes
    content_type: str
    fetched_at: datetime


class DomainRateLimiter:
    """Enforces a minimum interval between requests to the same domain."""

    def __init__(self, min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._last_request_at: dict[str, float] = {}

    def wait(self, domain: str) -> None:
        last = self._last_request_at.get(domain)
        now = time.monotonic()
        if last is not None:
            remaining = self.min_interval_seconds - (now - last)
            if remaining > 0:
                time.sleep(remaining)
                now = time.monotonic()
        self._last_request_at[domain] = now


class RobotsChecker:
    """Fetches and caches robots.txt per origin, then answers can-fetch checks."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _parser_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._parsers:
            parser = urllib.robotparser.RobotFileParser()
            try:
                response = self._client.get(
                    f"{origin}/robots.txt", headers={"User-Agent": USER_AGENT}
                )
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                else:
                    # No robots.txt (404 etc.) -> permissive by convention.
                    parser.parse([])
            except httpx.HTTPError:
                # Unreachable robots.txt: fail closed is safer than fail
                # open for a research bot — treat as disallow-all so a
                # transient robots.txt outage never becomes an accidental
                # scrape of a site that intended to restrict us.
                parser.parse(["User-agent: *", "Disallow: /"])
            self._parsers[origin] = parser
        return self._parsers[origin]

    def is_allowed(self, url: str, user_agent: str = USER_AGENT) -> bool:
        return self._parser_for(url).can_fetch(user_agent, url)


class Fetcher:
    """Fetches a `Source`'s content, subject to the access-policy checks above."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        rate_limiter: DomainRateLimiter | None = None,
        robots_checker: RobotsChecker | None = None,
        respect_robots: bool = True,
    ) -> None:
        self._client = client or httpx.Client(
            timeout=DEFAULT_TIMEOUT_SECONDS, follow_redirects=True
        )
        self._owns_client = client is None
        self.rate_limiter = rate_limiter or DomainRateLimiter()
        self.robots_checker = robots_checker or RobotsChecker(self._client)
        self.respect_robots = respect_robots

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def fetch(self, source: Source) -> FetchResult:
        """Fetch `source.url`, refusing paywalled/auth-required sources and
        robots-disallowed URLs before ever making a network call."""
        source.assert_fetchable()

        if self.respect_robots and not self.robots_checker.is_allowed(source.url):
            raise RobotsDisallowedError(
                f"robots.txt disallows fetching {source.url} for {USER_AGENT}"
            )

        domain = urlparse(source.url).netloc
        self.rate_limiter.wait(domain)

        try:
            response = self._fetch_with_retry(source.url)
        except httpx.HTTPError as exc:
            raise FetchError(
                f"Failed to fetch {source.url} after exhausting the retry budget: {exc}"
            ) from exc

        return FetchResult(
            url=str(response.url),
            status_code=response.status_code,
            content=response.content,
            content_type=response.headers.get("content-type", ""),
            fetched_at=datetime.now(UTC),
        )

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _fetch_with_retry(self, url: str) -> httpx.Response:
        response = self._client.get(url, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return response
