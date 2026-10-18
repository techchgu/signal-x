"""Conservative claim verification and evidence conflict classification."""
from collections import defaultdict
import re
from typing import Iterable
from src.schemas import ClaimVerification, Evidence, Finding


def uncited_findings(findings: list[Finding], evidence: list[Evidence]) -> list[str]:
    ids = {e.evidence_id for e in evidence}
    return [f.claim for f in findings if not f.evidence_ids or not set(f.evidence_ids).issubset(ids)]


def _usable(e: Evidence) -> bool:
    # Retrieved means text was extracted, not that its claims were verified.
    # It can be evaluated as a source, but one source alone cannot verify itself.
    return e.extraction_status in ("retrieved", "verified", "demo") and bool(e.excerpt.strip())


def _independent(a: Evidence, b: Evidence) -> bool:
    """A distinct publisher domain is a necessary but not sufficient condition."""
    af = (a.source_family or a.publisher).strip().lower()
    bf = (b.source_family or b.publisher).strip().lower()
    return bool(af and bf and af != bf)


def _quality(e: Evidence) -> str:
    if e.extraction_status == "demo":
        return "demo-only; not real-world verification"
    if e.extraction_status == "retrieved":
        if e.source_family.lower().endswith("sec.gov"):
            return "SEC public XBRL companyfacts record; extracted from SEC filing data, not independently corroborated"
        return "page retrieved; factual content not independently verified"
    if e.extraction_status != "verified" or not e.excerpt:
        return "unverified or inaccessible"
    host = e.source_family.lower()
    if host.endswith(".gov") or host.endswith(".sec.gov"):
        return "primary public filing/government domain; page text retrieved"
    if any(word in host for word in ("investor", "ir.")):
        return "likely issuer source; retrieved page, not independent"
    return "retrieved publisher webpage; editorial and source independence not independently assessed"


def _tokens(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9$%.-]+", text.lower()) if len(x) > 2}


def _semantic_overlap(a: str, b: str) -> float:
    left, right = _tokens(a), _tokens(b)
    return len(left & right) / max(1, len(left | right))


def _period_signature(text: str) -> set[str]:
    low = text.lower()
    def full_year(raw: str) -> str:
        return f"20{raw}" if len(raw) == 2 else raw
    quarter = {f"q{m.group(1)} {full_year(m.group(2))}"
               for m in re.finditer(r"\bq([1-4])\s*(?:fy\s*)?(20\d{2}|\d{2})\b", low)}
    quarter.update(f"q{m.group(2)} {full_year(m.group(1))}"
                   for m in re.finditer(r"\bfy\s*(20\d{2}|\d{2})\s*q([1-4])\b", low))
    quarter_words = {"first": "1", "second": "2", "third": "3", "fourth": "4"}
    for word, number in quarter_words.items():
        quarter.update(f"q{number} {m.group(1)}" for m in re.finditer(rf"\b{word} quarter\s+(20\d{{2}})\b", low))
    years = set()
    if not quarter:
        years.update(full_year(x) for x in re.findall(r"\bfy\s*(20\d{2}|\d{2})\b", low))
        years.update(re.findall(r"\b20\d{2}\b", low))
    return quarter or years


def _definition_signature(text: str) -> set[str]:
    known = {"gaap", "non-gaap", "adjusted", "constant currency", "organic", "excluding acquisition"}
    low = text.lower()
    return {term for term in known if term in low}


def _numeric_values(text: str) -> set[tuple[str, str]]:
    return {(m.group(1).replace(",", ""), (m.group(2) or "").lower())
            for m in re.finditer(r"\b(\d[\d,]*(?:\.\d+)?)\s*(%|percent|million|billion|thousand|m|bn|usd|eur|\$)?\b", text, re.I)}


def compare_evidence(a: Evidence, b: Evidence) -> list[str]:
    """Return cautious discrepancy notes, including period/definition distinctions."""
    if not (_usable(a) and _usable(b)):
        return []
    ta, tb = a.excerpt, b.excerpt
    same_topic = _semantic_overlap(ta, tb) >= 0.08
    if not same_topic:
        return []
    findings: list[str] = []
    pa, pb = _period_signature(ta), _period_signature(tb)
    if pa and pb and pa.isdisjoint(pb):
        findings.append(f"Different reporting periods in [{a.evidence_id}] and [{b.evidence_id}] ({', '.join(sorted(pa))} vs {', '.join(sorted(pb))}); not a like-for-like contradiction.")
    da, db = _definition_signature(ta), _definition_signature(tb)
    if da != db and (da or db):
        findings.append(f"Potentially different accounting/reporting definitions in [{a.evidence_id}] and [{b.evidence_id}] ({', '.join(sorted(da)) or 'unspecified'} vs {', '.join(sorted(db)) or 'unspecified'}); reconcile definitions before calling a contradiction.")
    va, vb = _numeric_values(ta), _numeric_values(tb)
    if va and vb and va.isdisjoint(vb) and not (pa and pb and pa.isdisjoint(pb)) and da == db:
        findings.append(f"Conflicting reported numeric values may appear in [{a.evidence_id}] and [{b.evidence_id}]; inspect metric definitions, scope, units, and filing context.")
    opposites = [("raised", "lowered"), ("increase", "decrease"), ("grew", "declined"),
                 ("growth", "decline"), ("beat", "missed"), ("positive", "negative"),
                 ("accelerated", "slowed")]
    if any((x in ta.lower() and y in tb.lower()) or (y in ta.lower() and x in tb.lower()) for x, y in opposites):
        if not (pa and pb and pa.isdisjoint(pb)):
            findings.append(f"Potentially conflicting directional explanations in [{a.evidence_id}] and [{b.evidence_id}]; manual context review required.")
    return findings


def verify_finding(finding: Finding, evidence: list[Evidence]) -> ClaimVerification:
    """Build a structured, evidence-constrained review for one candidate finding."""
    by_id = {e.evidence_id: e for e in evidence}
    supporting = [by_id[i] for i in finding.evidence_ids if i in by_id and _usable(by_id[i])]
    invalid = [i for i in finding.evidence_ids if i not in by_id]
    gaps: list[str] = []
    if not supporting:
        gaps.append("No cited, accessible source excerpt supports this claim.")
    if invalid:
        gaps.append("Unknown evidence IDs: " + ", ".join(invalid))
    cited = {e.evidence_id for e in supporting}
    related = ([] if finding.kind == "calculated result" else
               [e for e in evidence if _usable(e) and e.evidence_id not in cited and
                _semantic_overlap(finding.claim, e.excerpt) >= 0.05])
    corroborating = [e for e in related if any(_semantic_overlap(s.excerpt, e.excerpt) >= 0.08 for s in supporting)
                     and any(_independent(s, e) for s in supporting)]
    disconfirming = []
    discrepancies: list[str] = []
    for source in ([] if finding.kind == "calculated result" else supporting + related):
        for other in evidence:
            if source.evidence_id >= other.evidence_id or not _independent(source, other):
                continue
            discrepancies.extend(compare_evidence(source, other))
            if any(note.startswith("Potentially conflicting") or note.startswith("Conflicting reported") for note in compare_evidence(source, other)):
                if other.evidence_id not in disconfirming and other.evidence_id not in cited:
                    disconfirming.append(other.evidence_id)
    if not corroborating:
        gaps.append("Independent corroboration was not found among the supplied retrieved evidence; status remains unresolved or partial.")
    if finding.kind == "calculated result":
        gaps.append("No independent source was structurally matched to this calculation's exact metric and fiscal periods; the cited records are its reported input facts.")
    elif not related:
        gaps.append("No relevant disconfirming or alternative evidence was found in the supplied source set; this is not evidence that none exists.")
    alternatives = []
    text = finding.claim.lower()
    if any(word in text for word in ("growth", "increase", "revenue", "margin", "profit", "demand")):
        alternatives.append("The apparent change may reflect pricing, product/customer mix, acquisition or divestiture effects, foreign exchange, or a temporary comparison base rather than underlying volume or durable demand.")
    elif finding.kind in ("reported fact", "calculated result"):
        alternatives.append("The apparent difference may reflect reporting period, accounting definition, segment scope, unit, or restatement differences rather than an underlying change.")
    # Alternatives are candidate explanations only; they are not presented as supported facts.
    if disconfirming:
        status = "contradicted"
    elif not supporting:
        status = "unresolved"
    elif corroborating and not gaps:
        status = "verified"
    else:
        status = "partially_supported" if supporting else "unresolved"
    return ClaimVerification(claim=finding.claim, supporting_evidence_ids=[e.evidence_id for e in supporting],
                             source_quality={e.evidence_id: _quality(e) for e in supporting + related},
                             evidence_gaps=gaps, verification_status=status,
                             corroborating_evidence_ids=[e.evidence_id for e in corroborating],
                             disconfirming_evidence_ids=disconfirming,
                             discrepancies=list(dict.fromkeys(discrepancies)),
                             alternative_hypotheses=alternatives)


def verify_findings(findings: Iterable[Finding], evidence: list[Evidence]) -> list[ClaimVerification]:
    return [verify_finding(finding, evidence) for finding in findings]


def counter_hypothesis(question: str, hypothesis: str) -> str:
    return (f"Candidate alternative (not established by evidence): the apparent signal may reflect a one-off, reporting or mix effect rather than a durable change. "
            f"To test it, seek evidence that could disconfirm: {hypothesis or question}. Compare like-for-like periods and definitions, inspect original filings, "
            "and search for independent evidence that supports a different explanation. If none is available, mark the alternative unresolved.")
