# casino-research-agent (casino-intel)

An independent, personal research project into the online casino competitive landscape: an ingestion pipeline and CLI that build a structured, source-backed dataset about online casino brands and their operators, aimed at informing brand strategy, proposition design, acquisition strategy, and website UX.

Full requirements: [`docs/requirements.md`](docs/requirements.md). In scope: market size/growth, brand reach, acquisition economics, operator revenue, promotions/bonuses, product breadth, visual identity, registration/deposit/withdrawal journeys, trust/regulatory signals, and mobile app presence - with explicit tracking of evidence type, confidence, and source provenance throughout, since most of this data isn't publicly disclosed at brand level.

## Data sources

Ingestion scripts (`scripts/import_*.py`) pull from:

- Regulator registers: UK Gambling Commission, Malta Gaming Authority, Curaçao, Anjouan.
- Operator financials and traffic data.

Source policy and provenance requirements are documented in [`docs/source-policy.md`](docs/source-policy.md).

## Architecture

- Python 3.12, `pydantic`, `typer` CLI (`casino-intel`).
- Primary storage is a Google Sheets workbook (chosen for low overhead, easy schema changes, and human inspectability - see `docs/requirements.md` - with a planned migration path to PostgreSQL).
- Document extraction via `pdfplumber`/`pymupdf` (PDF), `beautifulsoup4`/`lxml` (HTML), `playwright` (dynamic pages).
- Built spec-first using [GitHub Spec Kit](https://github.com/github/spec-kit) (`.specify/`, `specs/001-casino-competitive-intelligence`).

## Setup

See [`docs/runbook.md`](docs/runbook.md) for full setup and operational procedures. In short:

```bash
pip install -e ".[dev]"
casino-intel initialise-workbook
```

Requires a Google Cloud service account with Sheets/Drive API access (`GOOGLE_APPLICATION_CREDENTIALS`, `SPREADSHEET_ID` - see `.env.example`).
