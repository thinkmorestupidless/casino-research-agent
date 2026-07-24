"""HTML parser (`beautifulsoup4` + `lxml` for structure/text, `pandas.read_html`
for tables) — source doc §11.1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO

import pandas as pd
from bs4 import BeautifulSoup


@dataclass
class HtmlParseResult:
    soup: BeautifulSoup
    tables: list[pd.DataFrame] = field(default_factory=list)
    text: str = ""


def parse_html(content: bytes | str, *, encoding: str = "utf-8") -> HtmlParseResult:
    """Parse raw HTML bytes/text into a soup, any `<table>`s as DataFrames,
    and the page's visible text (for KPI search-term scanning)."""
    text_content = (
        content.decode(encoding, errors="replace") if isinstance(content, bytes) else content
    )

    soup = BeautifulSoup(text_content, "lxml")

    try:
        tables = pd.read_html(StringIO(text_content))
    except (ValueError, ImportError):
        # No <table> elements found (or pandas couldn't find a parser
        # flavor to attempt one on a fragment this small) — not an error,
        # just nothing to extract as tabular data from this page.
        tables = []

    visible_text = soup.get_text(separator="\n", strip=True)

    return HtmlParseResult(soup=soup, tables=tables, text=visible_text)


def find_elements(result: HtmlParseResult, css_selector: str) -> list[str]:
    """Return the text content of every element matching `css_selector`,
    for extractors that locate a fact via a CSS-selector source locator."""
    return [el.get_text(strip=True) for el in result.soup.select(css_selector)]
