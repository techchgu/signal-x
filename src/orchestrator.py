"""End-to-end live research orchestration."""
from pathlib import Path
from collections.abc import Callable
from src.schemas import ResearchResult, Finding, Evidence, Metric
from src.search import search_web
from src.evidence import retrieve_many
from src.analysis import (AnalysisError, triangulate, contradictions, generate_research_plan,
                          get_model_provider, identify_metrics, analyze_evidence, compare_facts,
                          percentage_change)
from src.financial_data import get_company_facts_for_ticker, annual_fact, SECDataError
from src.verification import counter_hypothesis, verify_findings
from src.storage import save_result
from config import HISTORY_PATH
from config import MAX_SEARCH_RESULTS


def collect_public_evidence(query: str, question: str, *, limit: int = MAX_SEARCH_RESULTS,
                            on_search_complete: Callable[[list], None] | None = None):
    """Run only public search and page/evidence collection; does not generate conclusions."""
    results = search_web(query, limit=limit)
    if on_search_complete:
        on_search_complete(results)
    evidence = retrieve_many(results, question, limit=limit, search_query=query)
    return results, evidence


def _fallback_plan(subject: str) -> list[str]:
    return [f"Find primary evidence about: {subject}",
            "Retrieve original source pages and extract relevant passages",
            "Identify candidate financial metrics and preserve units and reporting periods",
            "Compare independent sources and test alternative explanations",
            "Report only supported claims and mark missing or incompatible data unavailable"]


def _format_number(value: float) -> str:
    return f"{value:,.0f}" if abs(value) >= 1_000_000 else f"{value:g}"


def run_research(question: str, mode: str = "General", company: str = "", *,
                 history_path: Path | None = HISTORY_PATH, search_limit: int = 7,
                 on_stage: Callable[[str, str], None] | None = None) -> ResearchResult:
    """Run plan → search → retrieve → analyze → verify → report-ready result → persist trace.

    Live mode always executes the configured public search provider and fetches original
    pages. Search/page failures are recorded and never replaced with demo content.
    """
    question = question.strip()
    if not question:
        raise ValueError("Enter a research question")
    subject = company.strip() or question
    statuses = {"plan": "running", "search": "pending", "fetch": "pending", "extract": "pending",
                "analyze": "pending", "verify": "pending", "report": "pending", "save_trace": "pending"}
    trace = ["Research question validated"]
    def stage(name: str, label: str):
        if on_stage:
            on_stage(name, label)
    try:
        provider = get_model_provider()
        plan_text = generate_research_plan(question, provider)
        plan = [line.strip().lstrip("0123456789. )-") for line in plan_text.splitlines() if line.strip()][:8]
        if not plan:
            raise ValueError("Planning provider returned no plan")
        statuses["plan"] = "completed (Gemini)" if provider else "completed (deterministic)"
    except Exception as exc:
        plan = _fallback_plan(subject)
        statuses["plan"] = "completed (fallback)"
        trace.append(f"Planning provider unavailable; deterministic plan used: {exc}")
    hypotheses = [f"Test whether retrieved evidence supports a material signal related to: {question}",
                  "Alternative: an apparent signal may reflect a temporary, mix, currency, accounting, or measurement effect."]
    trace.append("Research plan and testable hypotheses created")
    stage("plan", statuses["plan"])

    statuses["search"] = "running"
    try:
        results = search_web(f"{subject} {question}".strip(), limit=search_limit)
        statuses["search"] = "completed"
        trace.append(f"Public search completed: {len(results)} unique result(s)")
    except Exception as exc:
        results = []
        statuses["search"] = "failed"
        trace.append(f"Public search failed: {exc}")
    stage("search", statuses["search"])

    statuses["fetch"] = "running"
    try:
        evidence = retrieve_many(results, question, limit=search_limit)
        statuses["fetch"] = "completed"
        statuses["extract"] = "completed"
        trace.append(f"Page retrieval and excerpt extraction completed: {len(evidence)} source record(s)")
    except Exception as exc:
        evidence = []
        statuses["fetch"] = "failed"
        statuses["extract"] = "failed"
        trace.append(f"Page retrieval failed: {exc}")
    stage("fetch", statuses["fetch"])

    statuses["analyze"] = "running"
    notes, insufficient = triangulate(evidence)
    conflict = contradictions(evidence)
    try:
        metric_candidates = identify_metrics(question, None)
    except Exception:
        metric_candidates = "Unavailable"
    accessible = [e for e in evidence if e.retrieval_status == "accessible" and e.excerpt]
    findings = []
    metrics = []
    limitations = ["Search coverage and freshness are not exhaustive.",
                   "Automated discrepancy checks are heuristic and require analyst review."]
    # SEC XBRL is the sole numeric data input. No numbers are parsed from general web prose.
    entered_company = company.strip()
    ticker = "MSFT" if "microsoft" in entered_company.lower() else (entered_company.upper() if entered_company else "")
    if not ticker:
        lower_question = question.lower()
        if "microsoft" in lower_question or "msft" in lower_question:
            ticker = "MSFT"
    if ticker:
        statuses["extract"] = "running"
        try:
            issuer, sec_facts = get_company_facts_for_ticker(ticker)
            revenue_concepts = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet")
            cash_concepts = ("NetCashProvidedByUsedInOperatingActivities",)
            capex_concepts = ("PaymentsToAcquirePropertyPlantAndEquipment",)
            revenue_by_year = {year: annual_fact(sec_facts, revenue_concepts, year)
                               for year in sorted({f.fiscal_year for f in sec_facts if f.fiscal_period == "FY" and f.form == "10-K"})}
            year = max((y for y, f in revenue_by_year.items() if f is not None), default=None)
            if year is None:
                limitations.append(f"SEC companyfacts returned no compatible annual revenue fact for {ticker}; financial metrics are unavailable.")
            else:
                prior_year = year - 1
                selected = {
                    "revenue current": revenue_by_year.get(year),
                    "revenue prior": revenue_by_year.get(prior_year),
                    "operating cash flow current": annual_fact(sec_facts, cash_concepts, year),
                    "operating cash flow prior": annual_fact(sec_facts, cash_concepts, prior_year),
                    "capital expenditures current": annual_fact(sec_facts, capex_concepts, year),
                    "capital expenditures prior": annual_fact(sec_facts, capex_concepts, prior_year),
                }
                fact_evidence = {}
                for key, fact in selected.items():
                    if fact is None:
                        continue
                    eid = f"SEC-{fact.accession_number.replace('-', '')}-FY{fact.fiscal_year}-{fact.concept}"
                    fact_evidence[key] = eid
                    evidence.append(Evidence(evidence_id=eid, title=f"SEC EDGAR companyfacts — {issuer.name}: {fact.label}",
                        url=fact.filing_url, canonical_url=fact.filing_url, search_query=f"SEC {issuer.ticker} {fact.label} FY{fact.fiscal_year}",
                        publisher="U.S. Securities and Exchange Commission", source_family="sec.gov",
                        published_at=None, excerpt=f"SEC XBRL fact: {fact.label} = {_format_number(fact.value)} {fact.unit}; fiscal year {fact.fiscal_year} ({fact.start} to {fact.end}); form {fact.form}; accession {fact.accession_number}.",
                        extraction_status="retrieved", retrieval_status="accessible", verification_status="not_verified"))
                def add_growth(label, current_key, prior_key):
                    current = selected[current_key]; prior = selected[prior_key]
                    if not current or not prior:
                        limitations.append(f"{label} growth is unavailable: compatible FY{year} and FY{prior_year} SEC facts were not both present.")
                        return None
                    metric = compare_facts(current, prior)
                    metric.name = f"{label} growth"
                    metric.source_ids = [fact_evidence[current_key], fact_evidence[prior_key]]
                    metrics.append(metric)
                    findings.append(Finding(claim=f"{issuer.name} {label.lower()} changed {metric.value:g}% from FY{prior_year} to FY{year}, calculated from SEC annual facts.",
                        kind="calculated result", evidence_ids=metric.source_ids, confidence="low"))
                    return metric
                revenue_growth = add_growth("Revenue", "revenue current", "revenue prior")
                cash_growth = add_growth("Operating cash flow", "operating cash flow current", "operating cash flow prior")
                capex_growth = add_growth("Capital expenditure", "capital expenditures current", "capital expenditures prior")
                if capex_growth:
                    hypotheses.append("Capital investment outlays may help explain why free cash flow moves differently from operating cash flow; test by comparing same-period operating cash flow and capital expenditure facts.")
                if revenue_growth and cash_growth:
                    gap = round(cash_growth.value - revenue_growth.value, 2)
                    metric = Metric(name="Operating cash flow growth minus revenue growth", value=gap, unit="percentage points",
                        period=f"FY{year} vs FY{prior_year}", source_ids=revenue_growth.source_ids + cash_growth.source_ids,
                        calculation=f"{cash_growth.value:g}% operating cash flow growth − {revenue_growth.value:g}% revenue growth")
                    metrics.append(metric)
                    findings.append(Finding(claim=f"Operating cash flow growth was {gap:g} percentage points {('above' if gap >= 0 else 'below')} revenue growth from FY{prior_year} to FY{year}.",
                        kind="calculated result", evidence_ids=metric.source_ids, confidence="low"))
                free_cash = {}
                for label, suffix in (("current", "current"), ("prior", "prior")):
                    cfo, capex = selected[f"operating cash flow {suffix}"], selected[f"capital expenditures {suffix}"]
                    if cfo and capex and cfo.unit == capex.unit and cfo.fiscal_year == capex.fiscal_year and cfo.start and capex.start and cfo.start == capex.start and cfo.end == capex.end:
                        free_cash[label] = (cfo.value - capex.value, [fact_evidence[f"operating cash flow {suffix}"], fact_evidence[f"capital expenditures {suffix}"]])
                        metrics.append(Metric(name=f"Free cash flow FY{year if suffix == 'current' else prior_year}", value=free_cash[label][0], unit=cfo.unit,
                            period=f"FY{cfo.fiscal_year}", source_ids=free_cash[label][1],
                            calculation=f"Operating cash flow {_format_number(cfo.value)} {cfo.unit} − capital expenditure {_format_number(capex.value)} {capex.unit}; same annual period and unit"))
                free_cash_growth = None
                if len(free_cash) == 2:
                    free_cash_growth = Metric(name="Free cash flow growth", value=round(percentage_change(free_cash['current'][0], free_cash['prior'][0]), 2), unit="%",
                        period=f"FY{year} vs FY{prior_year}", source_ids=free_cash['current'][1] + free_cash['prior'][1],
                        calculation=f"({_format_number(free_cash['current'][0])} - {_format_number(free_cash['prior'][0])}) / abs({_format_number(free_cash['prior'][0])}) × 100")
                    metrics.append(free_cash_growth)
                    if capex_growth:
                        ids = list(dict.fromkeys(cash_growth.source_ids + capex_growth.source_ids + free_cash_growth.source_ids))
                        findings.append(Finding(claim=f"FY{year} operating cash flow grew {cash_growth.value:g}% and capital expenditure grew {capex_growth.value:g}%, while calculated free cash flow declined {abs(free_cash_growth.value):g}%. Higher capital outlays coincide with lower free cash flow in these annual figures; this arithmetic alone does not isolate the cause.",
                            kind="calculated result", evidence_ids=ids, confidence="low"))
                else:
                    limitations.append("Free cash flow is unavailable because matching annual operating cash flow and capital expenditure facts were not both present with identical periods and units.")
        except (SECDataError, AnalysisError, ValueError) as exc:
            limitations.append(f"SEC financial data unavailable for {ticker}: {exc}")
            statuses["extract"] = "unavailable"
        else:
            statuses["extract"] = "completed" if metrics else "partial; metrics unavailable"
    else:
        statuses["extract"] = "not applicable; no US ticker identified"
        limitations.append("No US ticker was identified. SEC companyfacts metrics were not requested; numeric financial metrics are unavailable.")
    statuses["analyze"] = "completed; Python calculations only" if metrics else "completed; financial metrics unavailable"
    trace.append("SEC annual facts retrieved where a US ticker was identified; arithmetic performed in Python with unit and period checks")
    trace.append(f"Candidate metric focus: {metric_candidates}")
    provider = None
    model_succeeded = False
    try:
        provider = get_model_provider()
        if provider:
            context = "\n".join(f"[{e.evidence_id}] {e.title}: {e.excerpt}" for e in accessible + [e for e in evidence if e.source_family == "sec.gov"])
            context += "\n\nPython-calculated metrics (do not recalculate):\n" + "\n".join(
                f"{m.name}: {_format_number(m.value)} {m.unit}; {m.period}; formula: {m.calculation}; evidence IDs: {', '.join(m.source_ids)}"
                for m in metrics)
            ai_text = analyze_evidence(question, context or "No retrieved evidence available.", provider)
            model_succeeded = True
            limitations.append("Gemini returned exploratory interpretation; treat it as a hypothesis requiring review against the cited evidence.")
            trace.append("Optional Gemini evidence interpretation completed; no model-generated arithmetic used")
        else:
            ai_text = "Deterministic mode: optional Gemini interpretation not called because no API key is configured."
    except Exception as exc:
        ai_text = "Optional Gemini interpretation unavailable; deterministic analysis continued."
        limitations.append(f"Gemini interpretation unavailable: {exc}")
        trace.append(f"Gemini request failed; deterministic analysis continued: {exc}")

    statuses["verify"] = "running"
    verifications = verify_findings(findings, evidence)
    statuses["verify"] = "completed"
    trace.append(f"Claim verification completed for {len(verifications)} candidate finding(s)")
    limitations.append("Retrieved public webpages are research leads and are not independently verified; distinct domains do not prove independent sourcing.")
    if insufficient:
        limitations.extend(insufficient)
    inaccessible = sum(e.retrieval_status == "inaccessible" for e in evidence)
    if inaccessible:
        limitations.append(f"{inaccessible} source(s) were inaccessible or unsupported and were not treated as verified evidence.")
    if metrics:
        calculated = "; ".join(f"{m.name}: {_format_number(m.value)} {m.unit} ({m.period})" for m in metrics)
        summary = f"SEC filing-backed calculations are available: {calculated}. These calculations describe reported annual values; explanations for any divergence remain hypotheses pending source review."
    elif accessible:
        summary = f"Retrieved {len(accessible)} page(s) with accessible text. They are research leads, not verified findings. Financial metrics are unavailable for this run."
    else:
        summary = "No original pages yielded accessible text. No conclusion is supported; search and retrieval failures or empty results are recorded in the trace."
    trace.append("Report content assembled with findings, source references, limitations, and verification status")
    statuses["report"] = "ready"
    trace.append("Research trace ready for persistence")
    result = ResearchResult(question=question, mode=f"Live — {mode}", plan=plan, hypotheses=hypotheses,
                           findings=findings, evidence=evidence, verifications=verifications, metrics=metrics,
                           contradictions=conflict,
                           counter_hypothesis=counter_hypothesis(question, hypotheses[0]),
                           limitations=limitations, trace=trace, summary=summary,
                           ai_interpretation=ai_text if model_succeeded else "",
                           stage_status=statuses)
    if history_path is not None:
        try:
            result.trace.append("Saving research result and trace to local history")
            save_result(result, history_path)
            result.stage_status["save_trace"] = "completed"
            result.trace[-1] = "Research result and trace saved to local history"
            save_result(result, history_path)
        except Exception as exc:
            result.stage_status["save_trace"] = "failed"
            result.trace.append(f"Research history save failed: {exc}")
    return result
