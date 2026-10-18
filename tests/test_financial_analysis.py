from unittest.mock import Mock
import pytest

from src.analysis import (AnalysisError, GeminiProvider, ModelProviderError, compare_facts,
                          generate_research_plan, get_model_provider,
                          percentage_change, ratio)
from src.financial_data import (Company, FinancialFact, SECDataError,
                               annual_fact, extract_facts, find_company, get_company_facts_for_ticker)


def fact(*, value, unit="USD", year=2025, period="FY", start="2025-01-01", end="2025-12-31", accession="0000000001-25-000001"):
    return FinancialFact(concept="Revenue", label="Revenue", value=value, unit=unit,
                         fiscal_period=period, fiscal_year=year, start=start, end=end,
                         form="10-K", accession_number=accession,
                         filing_url="https://www.sec.gov/Archives/edgar/data/1/000000000125000001/")


def test_percentage_change_and_ratio_arithmetic():
    assert percentage_change(120, 100) == 20
    assert percentage_change(80, 100) == -20
    assert ratio(20, 100, numerator_unit="USD", denominator_unit="USD") == 0.2


@pytest.mark.parametrize("fn,args", [
    (percentage_change, (None, 10)),
    (percentage_change, (10, None)),
    (ratio, (None, 10)),
    (ratio, (10, 0)),
])
def test_missing_and_zero_values_raise_clear_errors(fn, args):
    with pytest.raises(AnalysisError):
        if fn is ratio:
            fn(*args, numerator_unit="USD", denominator_unit="USD")
        else:
            fn(*args)


def test_zero_prior_change_and_incompatible_units_are_rejected():
    with pytest.raises(AnalysisError, match="zero"):
        percentage_change(10, 0)
    with pytest.raises(AnalysisError, match="Inconsistent units"):
        ratio(10, 5, numerator_unit="USD", denominator_unit="shares")


def test_fact_comparison_requires_same_units_and_compatible_duration():
    prior = fact(value=100, year=2024, start="2024-01-01", end="2024-12-31", accession="0000000001-24-000001")
    current = fact(value=125)
    metric = compare_facts(current, prior)
    assert metric.value == 25
    assert "FY2025" in metric.period and "FY2024" in metric.period
    assert metric.source_ids == [current.accession_number, prior.accession_number]
    with pytest.raises(AnalysisError, match="Inconsistent units"):
        compare_facts(fact(value=125, unit="EUR"), prior)
    with pytest.raises(AnalysisError, match="Inconsistent reporting periods"):
        compare_facts(fact(value=125, start="2025-10-01", end="2025-12-31"), prior)
    with pytest.raises(AnalysisError, match="duration facts"):
        compare_facts(fact(value=125, start=None), prior)
    with pytest.raises(AnalysisError, match="Inconsistent fiscal periods"):
        compare_facts(fact(value=125, period="Q4", start="2025-10-01"), prior)


def test_sec_extract_preserves_period_unit_and_filing_url():
    raw = {"cik": 1234, "facts": {"us-gaap": {"Revenues": {
        "label": "Revenue", "units": {"USD": [{"val": 120, "fy": 2025, "fp": "FY",
            "start": "2025-01-01", "end": "2025-12-31", "form": "10-K",
            "accn": "0000001234-26-000001"}]}}}}}
    fact_row, = extract_facts(raw, ["Revenues"])
    assert fact_row.value == 120 and fact_row.unit == "USD"
    assert fact_row.fiscal_year == 2025 and fact_row.fiscal_period == "FY"
    assert fact_row.filing_url.endswith("/000000123426000001/")


def test_sec_http_lookup_uses_mocked_public_response():
    response = Mock()
    response.json.return_value = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    get = Mock(return_value=response)
    company = find_company("aapl", get=get)
    assert company == Company(cik=320193, ticker="AAPL", name="Apple Inc.")
    assert "timeout" in get.call_args.kwargs
    with pytest.raises(SECDataError, match="not found"):
        get_company_facts_for_ticker("NONE", get=get)


def test_absent_api_key_selects_deterministic_plan():
    assert get_model_provider(api_key="") is None
    plan = generate_research_plan("revenue trend", provider=None)
    assert "Python" in plan and "revenue trend" in plan


def test_keyed_provider_reports_missing_sdk_or_api_failures_clearly():
    # Invalid credentials fail at request time; key presence is not represented as success.
    client = Mock()
    client.models.generate_content.side_effect = RuntimeError("denied")
    provider = GeminiProvider("test-key", client=client)
    with pytest.raises(ModelProviderError, match="Gemini request failed"):
        provider.generate("prompt")


def test_annual_fact_selection_rejects_quarter_and_incompatible_duration():
    rows = [fact(value=100), fact(value=20, period="Q4", start="2025-10-01", end="2025-12-31"),
            fact(value=30, start="2025-01-01", end="2025-06-30")]
    assert annual_fact(rows, ("Revenue",), 2025) == rows[0]
    assert annual_fact(rows, ("Revenue",), 2024) is None
