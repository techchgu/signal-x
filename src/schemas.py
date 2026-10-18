"""Validated records used across the research pipeline."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SearchResult(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str
    url: HttpUrl
    snippet: str = ""
    published_at: str | None = None


class Evidence(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    evidence_id: str
    title: str
    url: str
    canonical_url: str | None = None
    search_query: str = ""
    search_snippet: str = ""
    publisher: str = "Unknown"
    published_at: str | None = None
    retrieved_at: datetime = Field(default_factory=utc_now)
    excerpt: str = ""
    extraction_status: Literal["retrieved", "verified", "unverified", "inaccessible", "demo"]
    retrieval_status: Literal["accessible", "inaccessible"] = "accessible"
    verification_status: Literal["not_verified", "verified", "unresolved"] = "not_verified"
    source_family: str = ""
    error: str | None = None

    @field_validator("url")
    @classmethod
    def require_http_source(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("Evidence source URL must use HTTP or HTTPS")
        return value


class Metric(BaseModel):
    name: str
    value: float
    unit: str
    period: str
    source_ids: list[str]
    calculation: str = "Reported value"


class Finding(BaseModel):
    claim: str
    kind: Literal["reported fact", "calculated result", "interpretation", "hypothesis"]
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "low"


class ClaimVerification(BaseModel):
    claim: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    source_quality: dict[str, str] = Field(default_factory=dict)
    evidence_gaps: list[str] = Field(default_factory=list)
    verification_status: Literal["verified", "partially_supported", "unresolved", "contradicted"]
    corroborating_evidence_ids: list[str] = Field(default_factory=list)
    disconfirming_evidence_ids: list[str] = Field(default_factory=list)
    discrepancies: list[str] = Field(default_factory=list)
    alternative_hypotheses: list[str] = Field(default_factory=list)


class ResearchResult(BaseModel):
    question: str
    mode: str
    plan: list[str]
    hypotheses: list[str]
    findings: list[Finding]
    evidence: list[Evidence]
    verifications: list[ClaimVerification] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    counter_hypothesis: str = ""
    limitations: list[str] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
    summary: str = ""
    ai_interpretation: str = ""
    stage_status: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
