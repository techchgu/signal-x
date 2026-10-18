# SIGNALX — evidence-first financial research

SignalX is a local Streamlit MVP that searches the public web, retrieves original pages, preserves source evidence, optionally reads official SEC EDGAR company facts, calculates comparable annual growth metrics in Python, records limitations, and generates a downloadable Markdown report. It is designed to make research traceable; it does not provide investment advice or verified predictions.

## Windows PowerShell setup

Requires Python 3.11 or 3.12. Run these commands from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pytest
Copy-Item .env.example .env
streamlit run app.py
```

If activation is blocked, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate. `.env` is optional for the app and must stay local. For SEC access, edit `SEC_USER_AGENT` in `.env` to include an identifying application name and a real contact email, as requested by the SEC. Never commit that file.

Live research requires internet access. Search uses the replaceable DDGS provider; search availability and coverage can change. SEC company facts are requested when a US ticker is entered, or when Microsoft/MSFT appears in the question. Other companies receive public-web research, but no SEC metrics are inferred.

Optional Gemini interpretation uses Google's supported `google-genai` SDK. Set `GEMINI_API_KEY` in `.env` to enable planning and exploratory interpretation. A configured key does not guarantee it is valid; request failures are reported and deterministic calculations continue. No paid API is required. Without a key, the dashboard and saved demo work deterministically.

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use synthetic financial facts and mocked HTTP/search responses; they do not require paid services or live web access. For a fresh environment, install `requirements.txt` and `pytest` first.

## Workflow

1. Plan a question deterministically, or with optional Gemini.
2. Search public results using DDGS and retain titles, URLs, and snippets.
3. Fetch a bounded number of original HTTPS HTML pages with timeouts and response limits. Failed and unsupported pages remain visible.
4. Extract source-linked excerpts and assign stable evidence IDs. Retrieved pages are not automatically verified.
5. If a supported US ticker is identified, request SEC EDGAR company facts and preserve filing accession references, periods, units, source URLs, and evidence IDs.
6. Calculate year-over-year revenue and operating cash flow changes, the growth-rate difference, and compatible free cash flow using Python. Reject incompatible periods/units and state when facts are unavailable.
7. Review candidate claims, evidence gaps, possible conflicts, and alternative hypotheses. Domain difference alone is not proof of source independence.
8. Render a Markdown report, display it in Streamlit, and let the user download it. Runs and traces can be saved locally.

## Modes and data

- **Live research** runs real search and retrieval. SEC data is separately obtained from SEC EDGAR for a supported ticker. Reports preserve source IDs and original URLs.
- **Demo — saved evidence** loads `data/demo/evidence.json`, calculates illustrative sample growth, and explicitly labels its data as saved demonstration material. It does not call search, SEC, or Gemini.
- Live run history is written to `data/history.json`; saved report output goes to `data/reports/latest_report.md`. These user data files are ignored by Git.
- `data/demo/example_report.md` is the illustrative fixture report. `docs/EXAMPLE_RESEARCH_REPORT.md` is a live SEC-backed example captured during project verification; its source statuses and limitations are recorded in the report.

## Supported and unsupported

| Implemented | Not implemented / limitations |
| --- | --- |
| DDGS public search behind replaceable adapter; bounded results and errors | Guaranteed search uptime, exhaustive coverage, or reproducible provider ranking |
| Bounded HTTPS HTML fetching, timeouts, readable excerpts, title/date/canonical extraction, failed-page records | PDFs, JavaScript-only pages, authentication, paywall access, broad crawling, or robust public-service SSRF hardening |
| Evidence IDs, original URLs, retrieval timestamps and distinct retrieval/verification status | Automatic proof that a source is truthful or that two domains are independent |
| SEC companyfacts for US registrants and filing accession references | Full coverage of every ticker, all financial statement tags, custom fiscal normalization, non-US filings, currency conversion |
| Comparable annual revenue and operating cash flow growth, percentage-point difference, and compatible FCF using Python | Automatic extraction of arbitrary financial numbers from web prose, segment reconciliation, or analyst estimates |
| Optional Gemini planning and hypothesis-oriented interpretation through `google-genai` | Required AI access, guaranteed valid model output, or model-generated arithmetic |
| Findings, claim verification status, alternatives, limitations, Markdown download, saved run history | Automatic independent counter-evidence search for each claim; human source review remains necessary |
| No-key saved-evidence demo | Real-world financial claims from demo data; all demo figures are illustrative |

## Submission materials

See [docs/PROJECT_SYNOPSIS.md](docs/PROJECT_SYNOPSIS.md), [docs/INNOVATION_AND_IMPACT.md](docs/INNOVATION_AND_IMPACT.md), [docs/TECHNICAL_ARCHITECTURE.md](docs/TECHNICAL_ARCHITECTURE.md), [docs/EXECUTION_PLAN.md](docs/EXECUTION_PLAN.md), [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md), [docs/EVALUATION.md](docs/EVALUATION.md), and [docs/EXAMPLE_RESEARCH_REPORT.md](docs/EXAMPLE_RESEARCH_REPORT.md).

## Review and commit locally

```powershell
git status --short
git add .env.example .gitignore README.md app.py config.py requirements.txt src tests docs prompts data/demo
git status --short
git diff --cached --check
git diff --cached --stat
git diff --cached
git commit -m "Complete SignalX evidence research MVP"
```

Review the staged paths before committing. Do not stage `.env`, local run history, virtual environments, or API keys. No push or deployment is part of this project workflow.
