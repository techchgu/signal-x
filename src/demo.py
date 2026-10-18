"""Load checked, saved sample evidence for a reproducible demo."""
import json
from pathlib import Path
from src.schemas import ResearchResult, Evidence, Finding, Metric
from src.verification import counter_hypothesis, verify_findings
from src.analysis import growth_metric
from config import ROOT


def demo_result(path: Path | None = None) -> ResearchResult:
    path = path or ROOT / "data" / "demo" / "evidence.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    question = saved["question"]
    evidence = [Evidence.model_validate(item) for item in saved["evidence"]]
    current, prior = saved["current_revenue_millions"], saved["prior_revenue_millions"]
    metric = growth_metric("Illustrative revenue", current, prior, "USD millions",
                           "FY2025 versus FY2024", ["D1"])
    findings = [Finding(claim="Saved demo evidence reports illustrative revenue of $120 million for FY2025 and $100 million for FY2024 [D1]. These are example values, not claims about a real issuer.",
                        kind="reported fact", evidence_ids=["D1"], confidence="low"),
                Finding(claim="Using the saved demo values, year-over-year growth calculates to 20% [D1].", kind="calculated result", evidence_ids=["D1"], confidence="low")]
    verifications = verify_findings(findings, evidence)
    return ResearchResult(question=question, mode="Demo — saved evidence", plan=["Load checked sample evidence from data/demo/evidence.json", "Calculate the illustrative growth in Python", "Verify citations and source limitations"],
                          hypotheses=["The saved sample values illustrate positive year-over-year growth."],
                          findings=findings, evidence=evidence, verifications=verifications, metrics=[metric],
                          contradictions=["The second saved page repeats the issuer's sample figures and is not independent corroboration."],
                          counter_hypothesis=counter_hypothesis(question, "The sample demonstrates positive year-over-year growth"),
                          limitations=["This mode uses saved demonstration evidence, not live web retrieval.", "All sample values are illustrative and must not be treated as real financial data.", "The saved second page repeats the issuer data and does not independently corroborate it."],
                          trace=["Demo mode selected", f"Loaded {len(evidence)} saved evidence records from {path.name}", "Illustrative percentage change calculated in Python", "Evidence citations checked", "Report generated"],
                          stage_status={"plan": "completed", "search": "saved evidence", "fetch": "saved evidence", "extract": "completed", "analyze": "completed", "verify": "completed", "report": "completed", "save_trace": "completed"},
                          summary="DEMO — this report uses checked evidence saved with the project. Its sample figures are illustrative, not live research or real issuer data.")
