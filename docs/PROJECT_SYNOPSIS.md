# Project synopsis

## Problem

Public company research is spread across filings, earnings releases, and news pages. A reader can lose the source and reporting-period context behind a number, mistake a search snippet for a retrieved page, or compare unlike measures.

## Proposed solution

SIGNALX is a local research assistant that connects public search and page retrieval to source-linked evidence. For recognized US tickers it can retrieve SEC EDGAR company facts, preserve accession references and periods, and calculate comparable annual changes using Python. It separates retrieved evidence from verified claims and reports missing data and limitations.

## Objectives

- Preserve the original URL, title, date when available, retrieval timestamp, excerpt, and a unique evidence ID.
- Compare annual financial values only when period and unit checks pass.
- Keep arithmetic deterministic and auditable.
- Present possible explanations as hypotheses until source evidence corroborates them.
- Provide a saved-evidence demo and downloadable Markdown report without requiring an API key.

## Intended users

Students, analysts, and judges who need a reproducible starting point for public-company research and are willing to review the underlying sources.

## Boundary

SIGNALX is an MVP, not an investment recommendation, audited financial database, or substitute for reviewing the original filing.
