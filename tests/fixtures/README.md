# Golden fixtures

Parser/extractor tests must not depend on live network access (source doc §20.3) since external pages change over time. Each fixture below is added during the ingestion-pipeline work (User Story 2, tasks T063/T070) and referenced by the corresponding unit/integration test.

| Fixture | File | Added by | Used by |
|---|---|---|---|
| UKGC statistics XLSX | `ukgc_business_data.xlsx` | T063/T070 | `tests/unit/test_tabular_parser.py`, `tests/unit/test_ukgc_importer.py` |
| Operator annual-report PDF excerpt | `operator_annual_report_excerpt.pdf` | T070 | `tests/unit/test_pdf_parser.py`, `tests/unit/test_operator_report_importer.py` |
| Promotion-terms HTML | `promotion_terms.html` | T070 | `tests/unit/test_html_parser.py`, `tests/unit/test_offer_capture.py` |
| Traffic-tool CSV export | `traffic_export.csv` | T063 | `tests/unit/test_traffic_importer.py` |
| Google Trends CSV export | `trends_export.csv` | T063 | `tests/unit/test_trends_importer.py` |
| App-store capture (JSON) | `app_store_capture.json` | T063 | `tests/unit/test_app_store_importer.py` |
| UX audit payload (JSON) | `ux_audit_payload.json` | Phase 5 (US3) | `tests/integration/test_user_story_3.py` |

Fixtures are small, synthetic or heavily-trimmed excerpts constructed to exercise parser logic — not verbatim copies of copyrighted third-party report content.
