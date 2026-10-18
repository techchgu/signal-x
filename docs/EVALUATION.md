# Evaluation and final audit

## Automated tests actually run

- Created a fresh Python 3.12 virtual environment under `%TEMP%\signalx-final-audit-venv` and installed `requirements.txt` plus `pytest`.
- Ran `python -m pytest -q`: **38 passed** (2026-10-18; final run 12.28 seconds). Tests use mocked search, page responses, SEC fixtures, and synthetic financial facts; no paid APIs are required.
- The suite includes a Streamlit `AppTest`: app startup and the saved-evidence demo completed without `GEMINI_API_KEY`.
- Started Streamlit with `streamlit run app.py --server.headless true --server.port 8765`; `http://127.0.0.1:8765/_stcore/health` returned `ok`. The process was stopped after the check.
- Ran `git diff --check`: no whitespace errors.

## Live retrieval and SEC workflow actually run

On 2026-10-18, the live Microsoft pilot completed with no Gemini key. DDGS returned results, original public pages were retrieved, and SEC EDGAR companyfacts returned Microsoft annual facts for FY2025 and FY2026. The captured report has five accessible web pages and five source-linked findings; SEC API evidence records preserve filing accession references. This is one run, not a measurement of general search reliability.

Python calculations in that captured run:

- Revenue growth: **17.79%**, FY2026 versus FY2025.
- Operating cash flow growth: **34.35%**, same annual periods.
- Operating cash flow growth minus revenue growth: **16.56 percentage points**.
- Capital expenditure growth: **79.62%**.
- Free cash flow, using operating cash flow minus capital expenditure: **$66.987 billion** in FY2026 versus **$71.611 billion** in FY2025; calculated growth **−6.46%**.

These are arithmetic results from SEC XBRL facts and are not independently corroborated in this run. All five candidate findings are marked partially supported, with no disconfirming source found and no claim marked verified or contradicted. The report links the filing accession records and does not infer that increased capital spending is the sole cause of a free-cash-flow change. Review the original filings before use.

## Security and repository checks

- `.gitignore` excludes `.env`, virtual environments, caches, and local history; `git check-ignore` confirmed `.env`, `.venv`, and `data/history.json` are ignored.
- A scan for common Google/secret token patterns found no credential. The only `GEMINI_API_KEY` match was the environment-variable read in `config.py`; `.env` is absent.
- No commits, push, or deployment were performed.

## Known limitations

- DDGS coverage/ranking and public internet access vary. A network failure is not replaced with demo data.
- Retrieval is limited to bounded HTTPS HTML. PDF, JavaScript-rendered, access-controlled, rate-limited, or blocked pages can be unavailable.
- SEC XBRL tag selection is intentionally narrow and does not normalize currencies, issuer-specific definitions, segments, or every filing restatement. The app preserves periods and filing references for review.
- Evidence verification uses text/domain heuristics; it cannot prove truth or independent sourcing. No dedicated second search is issued for every claim.
- Optional Gemini output is displayed separately as an unverified interpretation. Gemini was not called in the documented live run.
- The app is a local prototype and is not hardened for unrestricted public deployment.
