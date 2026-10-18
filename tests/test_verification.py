from src.schemas import Evidence, Finding
from src.verification import compare_evidence, verify_finding, verify_findings


def ev(eid, host, excerpt, *, status="verified"):
    return Evidence(evidence_id=eid, title=eid, url=f"https://{host}/story", publisher=host,
                    source_family=host, excerpt=excerpt, extraction_status=status)


def test_insufficient_independent_evidence_stays_unresolved():
    source = ev("E1", "issuer.example", "The company reported revenue growth of 20 percent in FY2025.")
    finding = Finding(claim="Revenue grew 20 percent in FY2025", kind="reported fact", evidence_ids=["E1"])
    result = verify_finding(finding, [source])
    assert result.verification_status == "partially_supported"
    assert result.supporting_evidence_ids == ["E1"]
    assert not result.corroborating_evidence_ids
    assert any("Independent corroboration" in gap for gap in result.evidence_gaps)
    assert result.alternative_hypotheses


def test_independent_disagreement_is_reported_as_potential_conflict():
    first = ev("E1", "issuer.example", "The company reported revenue of $120 million, growth of 20 percent in FY2025.")
    second = ev("E2", "news.example", "Revenue was $110 million, a decline of 5 percent in FY2025, analysts report.")
    notes = compare_evidence(first, second)
    assert any("Conflicting reported numeric values" in note for note in notes)
    assert any("Potentially conflicting directional" in note for note in notes)
    finding = Finding(claim="The company reported revenue of $120 million growth in FY2025", kind="reported fact", evidence_ids=["E1"])
    result = verify_finding(finding, [first, second])
    assert result.verification_status == "contradicted"
    assert "E2" in result.disconfirming_evidence_ids
    assert any("Conflicting reported numeric values" in item for item in result.discrepancies)


def test_different_periods_are_not_mislabeled_as_contradiction():
    q4 = ev("E1", "issuer.example", "Revenue increased to $120 million in Q4 2025.")
    q3 = ev("E2", "news.example", "Revenue declined to $100 million in Q3 2025.")
    notes = compare_evidence(q4, q3)
    assert any("Different reporting periods" in note and "not a like-for-like contradiction" in note for note in notes)
    assert not any("Potentially conflicting directional" in note for note in notes)


def test_fiscal_short_year_quarters_are_recognized_as_different_periods():
    q4_25 = ev("E1", "issuer.example", "FY25 Q4 revenue was $70 billion.")
    q4_26 = ev("E2", "news.example", "FY2026 Q4 revenue was $80 billion.")
    notes = compare_evidence(q4_25, q4_26)
    assert any("Different reporting periods" in note and "not a like-for-like contradiction" in note for note in notes)
    assert not any("Conflicting reported numeric values" in note for note in notes)


def test_calculated_claim_is_not_contradicted_by_unmatched_webpage_numbers():
    inputs = [ev("E1", "sec.gov", "Revenue = 331,839,000,000 USD; FY2026."),
              ev("E2", "sec.gov", "Revenue = 281,724,000,000 USD; FY2025.")]
    article = ev("E3", "news.example", "Microsoft FY25 Q4 reported 70 billion revenue; FY26 Q4 reported 80 billion.")
    finding = Finding(claim="Revenue grew 17.79% from FY2025 to FY2026", kind="calculated result", evidence_ids=["E1", "E2"])
    result = verify_finding(finding, inputs + [article])
    assert result.verification_status == "partially_supported"
    assert result.disconfirming_evidence_ids == []
    assert result.corroborating_evidence_ids == []


def test_accounting_definition_difference_is_flagged_for_reconciliation():
    a = ev("E1", "issuer.example", "GAAP operating income was $20 million in FY2025.")
    b = ev("E2", "news.example", "Adjusted operating income was $25 million in FY2025.")
    notes = compare_evidence(a, b)
    assert any("different accounting/reporting definitions" in note for note in notes)
    assert not any("Conflicting reported numeric values" in note for note in notes)


def test_inaccessible_sources_are_gaps_not_support():
    inaccessible = ev("E1", "issuer.example", "", status="inaccessible")
    finding = Finding(claim="Revenue grew", kind="hypothesis", evidence_ids=["E1"])
    result, = verify_findings([finding], [inaccessible])
    assert result.verification_status == "unresolved"
    assert result.supporting_evidence_ids == []
    assert any("No cited, accessible" in gap for gap in result.evidence_gaps)
