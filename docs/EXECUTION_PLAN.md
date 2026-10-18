# Execution plan and feasibility

## Implemented MVP

1. Accept a research question and optional company/ticker.
2. Create a deterministic plan, with optional Gemini planning.
3. Search DDGS and retrieve a bounded number of public HTTPS HTML pages.
4. Preserve accessible and failed page records with IDs, URLs, dates when available, excerpts, and status.
5. For an identified US ticker, retrieve SEC XBRL company facts and select comparable annual revenue, operating cash flow, and capital expenditure facts.
6. Compute growth, percentage-point difference, and compatible free cash flow in Python.
7. Review evidence references and likely conflicts, disclose unresolved support, and generate a Markdown report.
8. Save run history locally; provide a no-key saved-evidence demo.

## Feasibility

The prototype uses Python, Streamlit, Requests, BeautifulSoup, Pandas, Pydantic, DDGS, and the optional official Gemini SDK already declared by the project. The SEC and web paths use public endpoints; network availability, SEC fair-access limits, search-provider changes, and publisher restrictions remain operational dependencies.

## Main risks and mitigations

- **Wrong XBRL tag or period selection:** retain tags and accession references, enforce annual-duration filters, show calculation formulas, and require analyst review.
- **Page inaccessible or changed:** retain the original URL and explicit failure reason; do not substitute snippets as page evidence.
- **False corroboration:** keep retrieved records unverified and label domain comparison as heuristic.
- **Model error or prompt injection:** make the model optional; label interpretation exploratory; treat retrieved text as untrusted; keep arithmetic in Python.
- **Sensitive key exposure:** `.env` is ignored, keep keys out of saved results, and review staged paths before committing.

## Planned improvements (not implemented)

- Claim-specific, independent searches for corroboration and disconfirming evidence.
- Broader tagged XBRL support with issuer-specific validation and definition reconciliation.
- PDF/filing document parsing, multi-currency handling with explicit exchange-rate provenance, and deeper segment analysis.
- More robust URL/DNS controls before any public deployment.
- Human evaluation of extraction accuracy, source independence, and usability.
