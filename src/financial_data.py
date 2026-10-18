"""SEC EDGAR company facts with explicit periods, units, and filing references."""
from dataclasses import dataclass
from datetime import date
import re
from typing import Any
import requests
from config import SEC_USER_AGENT, REQUEST_TIMEOUT

SEC_HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"


class SECDataError(RuntimeError):
    """A public SEC request or response could not provide usable data."""


@dataclass(frozen=True)
class FinancialFact:
    concept: str
    label: str
    value: float
    unit: str
    fiscal_period: str
    fiscal_year: int
    start: str | None
    end: str
    form: str
    accession_number: str
    filing_url: str
    frame: str | None = None


@dataclass(frozen=True)
class Company:
    cik: int
    ticker: str
    name: str


def _get_json(url: str, *, get=requests.get) -> Any:
    try:
        response = get(url, headers=SEC_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise SECDataError(f"SEC request failed for {url}: {exc}") from exc


def find_company(ticker: str, *, get=requests.get) -> Company | None:
    """Find a US registrant by ticker. Return None only when ticker is absent."""
    needle = ticker.strip().upper()
    if not needle:
        raise ValueError("Ticker cannot be empty")
    rows = _get_json(SEC_TICKERS_URL, get=get)
    for row in rows.values():
        if row.get("ticker", "").upper() == needle:
            return Company(cik=int(row["cik_str"]), ticker=needle, name=row["title"])
    return None


def company_facts(cik: int, *, get=requests.get) -> dict:
    """Get raw SEC companyfacts JSON; network/API failures raise SECDataError."""
    if not 1 <= int(cik) <= 99_999_999_999:
        raise ValueError("CIK must be a positive integer")
    return _get_json(SEC_FACTS_URL.format(cik=int(cik)), get=get)


def _fact_from_row(concept: str, label: str, unit: str, row: dict, cik: int = 0) -> FinancialFact | None:
    try:
        accn = str(row["accn"])
        end = date.fromisoformat(row["end"]).isoformat()
        start = date.fromisoformat(row["start"]).isoformat() if row.get("start") else None
        fy, fp, form = int(row["fy"]), str(row["fp"]), str(row["form"])
        value = float(row["val"])
        if not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accn):
            return None
        return FinancialFact(concept=concept, label=label, value=value, unit=unit,
                             fiscal_period=fp, fiscal_year=fy, start=start, end=end, form=form,
                             accession_number=accn,
                             filing_url=f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/",
                             frame=row.get(" frame"))
    except (KeyError, TypeError, ValueError):
        return None


def extract_facts(data: dict, concepts: list[str] | None = None,
                  forms: tuple[str, ...] = ("10-K", "10-Q")) -> list[FinancialFact]:
    """Flatten selected GAAP facts without converting their units or periods.

    Filing references are derived from the CIK embedded in SEC filing metadata
    when available, or from the top-level CIK. Unsupported rows are skipped.
    """
    facts = data.get("facts", {}).get("us-gaap", {})
    wanted = set(concepts) if concepts else set(facts)
    cik = int(data.get("cik", 0) or 0)
    output: list[FinancialFact] = []
    for concept in sorted(wanted):
        record = facts.get(concept)
        if not record:
            continue
        for unit, rows in record.get("units", {}).items():
            for row in rows:
                if row.get("form") not in forms:
                    continue
                fact = _fact_from_row(concept, record.get("label", concept), unit, row, cik)
                if not fact:
                    continue
                filing_url = fact.filing_url
                if cik:
                    filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{fact.accession_number.replace('-', '')}/"
                output.append(FinancialFact(**{**fact.__dict__, "filing_url": filing_url}))
    return output


def get_company_facts_for_ticker(ticker: str, *, get=requests.get) -> tuple[Company, list[FinancialFact]]:
    company = find_company(ticker, get=get)
    if company is None:
        raise SECDataError(f"Ticker {ticker.strip().upper()} was not found in SEC ticker data")
    raw = company_facts(company.cik, get=get)
    raw["cik"] = company.cik
    return company, extract_facts(raw)


def annual_fact(facts: list[FinancialFact], concepts: tuple[str, ...], fiscal_year: int) -> FinancialFact | None:
    """Select a compatible full-year 10-K duration fact; never substitute a quarter/YTD fact."""
    candidates = []
    for fact in facts:
        if fact.concept not in concepts or fact.fiscal_period != "FY" or fact.fiscal_year != fiscal_year:
            continue
        if fact.form != "10-K" or not fact.start:
            continue
        try:
            duration = (date.fromisoformat(fact.end) - date.fromisoformat(fact.start)).days
        except ValueError:
            continue
        if 350 <= duration <= 380:
            candidates.append(fact)
    # Prefer the latest filing for restated comparative values, but do not mix tags.
    priority = {concept: index for index, concept in enumerate(concepts)}
    return min(candidates, key=lambda item: (priority[item.concept], -date.fromisoformat(item.end).toordinal(), item.accession_number)) if candidates else None
