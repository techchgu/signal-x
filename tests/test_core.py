import json
from pathlib import Path
from unittest.mock import patch
import pytest
from src.analysis import yoy_growth, triangulate
from src.demo import demo_result
from src.report import render_report
from src.schemas import Evidence, Finding
from src.verification import uncited_findings
from src.orchestrator import run_research, collect_public_evidence
from src.storage import save_result
from src.storage import load_results
from src.schemas import SearchResult


def test_yoy_growth():
    assert yoy_growth(120, 100) == 20
    assert yoy_growth(80, 100) == -20
    with pytest.raises(ValueError): yoy_growth(10, 0)


def test_citations_and_report():
    result = demo_result()
    assert not uncited_findings(result.findings, result.evidence)
    report = render_report(result)
    assert "DEMO DATA" in report and "20%" in report and "https://example.com" in report


def test_missing_citation_is_reported():
    assert uncited_findings([Finding(claim="unsupported", kind="hypothesis")], []) == ["unsupported"]


def test_domains_required_for_triangulation():
    e = Evidence(evidence_id="x", title="t", url="https://a.example/x", publisher="a",
                 source_family="example", excerpt="x"*100, extraction_status="verified")
    assert not triangulate([e])[0]
    e2 = e.model_copy(update={"evidence_id":"y", "source_family":"other.example"})
    assert triangulate([e,e2])[0]


def test_search_failure_is_traceable_and_not_fabricated():
    with patch("src.orchestrator.search_web", side_effect=RuntimeError("offline")):
        result = run_research("test question", history_path=None)
    assert not result.evidence and not result.findings
    assert any("offline" in entry for entry in result.trace)
    assert "No original pages" in result.summary


def test_storage_roundtrip(tmp_path: Path):
    path = tmp_path / "history.json"
    save_result(demo_result(), path)
    assert json.loads(path.read_text(encoding="utf-8"))[0]["mode"].startswith("Demo")
    assert load_results(path)[0].mode.startswith("Demo")
    assert load_results(path, limit=0) == []


def test_live_orchestration_runs_and_persists_full_trace(tmp_path: Path):
    evidence = Evidence(evidence_id="LIVE1", title="Retrieved page", url="https://news.example/page",
                        publisher="News", source_family="news.example", excerpt="The business reported a major change in customer demand for its products this year.",
                        extraction_status="verified")
    path = tmp_path / "history.json"
    with patch("src.orchestrator.get_model_provider", return_value=None), \
         patch("src.orchestrator.search_web", return_value=[SearchResult(title="Result", url="https://news.example/page")]) as search, \
         patch("src.orchestrator.retrieve_many", return_value=[evidence]):
        result = run_research("What changed in demand?", history_path=path)
    assert search.called
    assert result.mode.startswith("Live")
    assert result.stage_status["search"] == "completed"
    assert result.stage_status["verify"] == "completed"
    assert result.stage_status["save_trace"] == "completed"
    assert result.evidence[0].url == "https://news.example/page"
    assert len(load_results(path)) == 1
    assert any("saved to local history" in line for line in result.trace)


def test_saved_demo_mode_is_explicit_and_uses_checked_file():
    result = demo_result()
    report = render_report(result)
    assert result.mode.startswith("Demo")
    assert result.stage_status["search"] == "saved evidence"
    assert "does not search the live web" in report
    assert all(item.extraction_status == "demo" for item in result.evidence)


def test_live_collection_uses_real_search_and_retrieval_adapters_without_conclusions():
    search_result = SearchResult(title="Source title", url="https://source.example/article", snippet="search snippet")
    evidence = Evidence(evidence_id="E1", title="Fetched title", url="https://source.example/article",
                        search_query="Acme revenue", search_snippet="search snippet", publisher="source.example",
                        source_family="source.example", excerpt="Relevant source page excerpt.",
                        extraction_status="retrieved", retrieval_status="accessible",
                        verification_status="not_verified")
    with patch("src.orchestrator.search_web", return_value=[search_result]) as search, \
         patch("src.orchestrator.retrieve_many", return_value=[evidence]) as retrieve:
        progress = []
        results, records = collect_public_evidence("Acme revenue", "revenue", limit=3,
                                                   on_search_complete=lambda found: progress.append(found))
    search.assert_called_once_with("Acme revenue", limit=3)
    retrieve.assert_called_once_with([search_result], "revenue", limit=3, search_query="Acme revenue")
    assert results == [search_result] and records == [evidence]
    assert progress == [[search_result]]


def test_live_orchestrator_calculates_only_comparable_sec_annual_facts():
    from src.financial_data import Company, FinancialFact
    accession = "0000000001-25-000001"
    filing = "https://www.sec.gov/Archives/edgar/data/1/000000000125000001/"
    def fact_row(concept, label, value, year, unit="USD"):
        return FinancialFact(concept=concept, label=label, value=value, unit=unit, fiscal_period="FY",
            fiscal_year=year, start=f"{year}-01-01", end=f"{year}-12-31", form="10-K",
            accession_number=accession, filing_url=filing)
    facts = [fact_row("Revenues", "Revenue", 120, 2025), fact_row("Revenues", "Revenue", 100, 2024),
             fact_row("NetCashProvidedByUsedInOperatingActivities", "Operating cash flow", 50, 2025),
             fact_row("NetCashProvidedByUsedInOperatingActivities", "Operating cash flow", 40, 2024),
             fact_row("PaymentsToAcquirePropertyPlantAndEquipment", "Capital expenditures", 10, 2025),
             fact_row("PaymentsToAcquirePropertyPlantAndEquipment", "Capital expenditures", 8, 2024)]
    with patch("src.orchestrator.get_model_provider", return_value=None), \
         patch("src.orchestrator.search_web", return_value=[]), \
         patch("src.orchestrator.retrieve_many", return_value=[]), \
         patch("src.orchestrator.get_company_facts_for_ticker", return_value=(Company(1, "MSFT", "Microsoft Corporation"), facts)):
        result = run_research("Does Microsoft's revenue align with cash flow?", company="Microsoft", history_path=None)
    assert next(m for m in result.metrics if m.name == "Revenue growth").value == 20
    assert next(m for m in result.metrics if m.name == "Operating cash flow growth").value == 25
    assert next(m for m in result.metrics if m.unit == "percentage points").value == 5
    assert next(m for m in result.metrics if m.name == "Free cash flow FY2025").value == 40
    ids = [e.evidence_id for e in result.evidence]
    assert len(ids) == len(set(ids))
    assert all(set(f.evidence_ids).issubset(ids) for f in result.findings)
    assert all(v.verification_status != "verified" for v in result.verifications)
