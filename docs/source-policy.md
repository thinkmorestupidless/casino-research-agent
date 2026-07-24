# Source access policy

This system collects only publicly accessible information, obtained lawfully and without bypassing access controls (spec.md FR-013, FR-046-FR-048).

## Rules enforced in code (not just policy)

- **Paywalled or authentication-required sources are never fetched automatically.** `Source.paywalled` / `Source.authentication_required` are checked in `src/casino_intel/fetching/fetcher.py` before any request is made; a `true` value causes the fetcher to refuse and route the source to a manual-capture research task instead.
- **robots.txt and site terms are checked before fetching.** The fetcher performs a robots-rules check per domain and respects `Disallow` rules.
- **Rate limiting is per-domain**, using conservative default delays, to avoid placing undue load on any single site.
- **No anti-bot bypass.** The fetcher does not attempt to defeat CAPTCHA, fingerprint spoofing, or other bot-detection countermeasures. A source that cannot be fetched without such measures is treated as inaccessible.
- **No account creation, deposits, wagers, or withdrawals** are ever performed by any automated or guided capture flow (`src/casino_intel/services/journey_safety.py` enforces the stop points for UX/brand audits).
- **No personal data about individual gamblers** is collected. Review/complaint content is aggregated and paraphrased (`src/casino_intel/parsing/reputation_importer.py`), never stored as raw text or usernames.

## Source priority

1. Statutory and regulatory sources
2. Operator primary sources
3. Brand primary sources
4. Reputable measurement platforms
5. Reputable secondary reporting
6. Affiliate and review sources
7. Inference

Conflicting sources are retained as separate observations — never silently reconciled (source doc §10.1).

## Legal disclaimer

Brand and UX analysis produced by this system informs strategy but does not constitute legal advice regarding gambling advertising or licensing compliance.
