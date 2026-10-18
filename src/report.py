"""Human-readable Markdown report rendering."""
from src.schemas import ResearchResult
from src.verification import uncited_findings


def _format_value(value: float) -> str:
    return f"{value:,.0f}" if abs(value) >= 1_000_000 else f"{value:g}"


def render_report(r: ResearchResult) -> str:
    lines = [f"# SignalX Research Report", "", f"**Question:** {r.question}", f"**Scope:** {r.mode}; public web search and retrieval, with SEC annual companyfacts when a supported US ticker is identified.", f"**Mode:** {r.mode}",
             f"**Created (UTC):** {r.created_at.isoformat()}", "", "## Executive summary", "", r.summary,
             "", "## Findings", ""]
    if r.mode.startswith("Demo"):
        lines += ["> **DEMO — SAVED EVIDENCE:** This report uses the checked evidence dataset saved with this project and does not search the live web.", ""]
    if r.ai_interpretation:
        lines += ["## Exploratory AI interpretation — unverified", "", r.ai_interpretation,
                  "", "This model output is an exploratory hypothesis, not a verified finding. Check every factual statement against the linked evidence.", ""]
    if r.findings:
        lines += [f"- **{f.kind.title()} ({f.confidence} confidence):** {f.claim}" for f in r.findings]
    else: lines.append("No supported findings from retrieved sources.")
    lines += ["", "## Evidence", ""]
    if not r.evidence: lines.append("No search results were available.")
    for e in r.evidence:
        lines += [f"### [{e.evidence_id}] {e.title}", f"- URL: [{e.url}]({e.url})", f"- Publisher: {e.publisher}",
                  f"- Published: {e.published_at or 'Not identified'}", f"- Retrieved: {e.retrieved_at.isoformat()}",
                  f"- Extraction status: {e.extraction_status}", f"- Retrieval status: {e.retrieval_status}",
                  f"- Verification status: {e.verification_status}", f"- Excerpt: {e.excerpt or 'No excerpt extracted.'}", ""]
    lines += ["## Financial metrics and calculations", ""]
    if r.metrics:
        for m in r.metrics:
            lines.append(f"- **{m.name}:** {_format_value(m.value)} {m.unit} ({m.period}). {m.calculation}. Sources: {', '.join(m.source_ids)}.")
    else: lines.append("No comparable financial metrics were extracted in this run.")
    lines += ["", "## Conclusion and next steps", ""]
    if r.metrics:
        lines.append("The listed calculations compare the reported periods and units shown. They establish a measured difference in growth rates, but do not by themselves establish its cause or persistence.")
    else:
        lines.append("Available evidence does not support a comparable financial conclusion in this run.")
    lines.append("Review the linked source filings and excerpts, confirm metric definitions and periods, and seek independent evidence for any proposed explanation.")
    lines += ["", "## Contradictions", ""] + ([f"- {c}" for c in r.contradictions] or ["No automated contradiction flags; this does not establish agreement."])
    lines += ["", "## Claim verification", ""]
    if r.verifications:
        for v in r.verifications:
            lines += [f"### {v.verification_status.replace('_', ' ').title()}: {v.claim}",
                      f"- Supporting evidence: {', '.join(v.supporting_evidence_ids) or 'None'}",
                      f"- Corroborating evidence: {', '.join(v.corroborating_evidence_ids) or 'None found'}",
                      f"- Disconfirming evidence: {', '.join(v.disconfirming_evidence_ids) or 'None found'}"]
            lines += [f"- Evidence gap: {gap}" for gap in v.evidence_gaps]
            lines += [f"- Discrepancy: {item}" for item in v.discrepancies]
            lines += [f"- Alternative hypothesis (unverified): {item}" for item in v.alternative_hypotheses]
    else:
        lines.append("No candidate findings were available for structured verification.")
    lines += ["", "## Workflow status", ""]
    if r.stage_status:
        lines += [f"- **{stage.replace('_', ' ').title()}:** {status}" for stage, status in r.stage_status.items()]
    else:
        lines.append("Stage status unavailable for this saved result.")
    lines += ["", "## Counterarguments", ""]
    alternatives = [alternative for verification in r.verifications for alternative in verification.alternative_hypotheses]
    lines += [f"- {alternative}" for alternative in alternatives] if alternatives else ["No evidence-specific counterargument was established; see candidate counter-hypothesis below."]
    lines += ["", "## Counter-hypothesis and falsification", "", r.counter_hypothesis, "", "## Methodology", ""]
    lines += [f"{i}. {step}" for i, step in enumerate(r.plan, 1)]
    lines += ["", "## Limitations and uncertainty", ""] + ([f"- {x}" for x in r.limitations] or ["No additional limitations recorded."])
    bad = uncited_findings(r.findings, r.evidence)
    lines += ["", "## Citation integrity", "", f"Unresolved uncited or invalidly cited findings: {len(bad)}.",
              "", "## Research trace", ""] + [f"- {x}" for x in r.trace]
    return "\n".join(lines) + "\n"
