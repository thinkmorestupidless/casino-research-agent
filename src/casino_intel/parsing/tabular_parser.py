"""CSV/XLSX parser (`pandas`/`openpyxl`) — source doc §11.1."""

from __future__ import annotations

import io

import pandas as pd


def parse_csv(content: bytes, **read_csv_kwargs: object) -> pd.DataFrame:
    """Parse CSV bytes into a DataFrame. Raises `pandas.errors.ParserError`
    (a subclass of ValueError) on malformed input rather than guessing."""
    return pd.read_csv(io.BytesIO(content), **read_csv_kwargs)


def parse_xlsx(
    content: bytes,
    *,
    sheet_name: str | int | None = 0,
    **read_excel_kwargs: object,
) -> pd.DataFrame | dict[str, pd.DataFrame]:
    """Parse XLSX bytes into a DataFrame (single sheet) or a dict of
    DataFrames keyed by sheet name (`sheet_name=None`)."""
    return pd.read_excel(
        io.BytesIO(content), sheet_name=sheet_name, engine="openpyxl", **read_excel_kwargs
    )
