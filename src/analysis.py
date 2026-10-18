"""Financial calculations, period/unit validation, and optional Gemini planning."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from src.schemas import Evidence, Metric
from src.financial_data import FinancialFact
from config import GEMINI_API_KEY, GEMINI_MODEL, ROOT


class AnalysisError(ValueError):
    """Input data cannot support the requested financial calculation."""


class ModelProviderError(RuntimeError):
    """Optional language-model provider failed or returned unusable output."""


def _number(value: float) -> str:
    return f"{value:,.0f}" if abs(value) >= 1_000_000 else f"{value:g}"


class TextModelProvider(Protocol):
    def generate(self, prompt: str) -> str: ...


class GeminiProvider:
    """Gemini provider implemented with Google's supported google-genai SDK."""
    def __init__(self, api_key: str, model: str = GEMINI_MODEL, *, client=None):
        if not api_key or not api_key.strip():
            raise ModelProviderError("GEMINI_API_KEY is not configured")
        if client is None:
            try:
                from google import genai
                client = genai.Client(api_key=api_key.strip())
            except Exception as exc:
                raise ModelProviderError("Gemini SDK is unavailable or could not initialize; install/update google-genai and check configuration") from exc
        self._client = client
        self._model = model

    def generate(self, prompt: str) -> str:
        try:
            response = self._client.models.generate_content(model=self._model, contents=prompt)
            text = getattr(response, "text", None)
            if not text or not text.strip():
                raise ModelProviderError("Gemini returned an empty response")
            return text.strip()
        except ModelProviderError:
            raise
        except Exception as exc:
            raise ModelProviderError(f"Gemini request failed: {exc}") from exc


def get_model_provider(api_key: str | None = None, model: str | None = None) -> TextModelProvider | None:
    """Return Gemini only when an environment/API key is present; absent key means deterministic mode."""
    key = GEMINI_API_KEY if api_key is None else api_key
    if not key or not key.strip():
        return None
    return GeminiProvider(key, model or GEMINI_MODEL)


def _prompt(name: str) -> str:
    path = ROOT / "prompts" / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ModelProviderError(f"Required prompt file is unavailable: {path}") from exc


def generate_research_plan(question: str, provider: TextModelProvider | None = None) -> str:
    """Create a bounded plan; without Gemini return a deterministic plan."""
    if not question.strip():
        raise ValueError("Research question cannot be empty")
    if provider is None:
        return "\n".join([f"1. Identify primary sources relevant to: {question.strip()}",
                         "2. Select testable hypotheses and evidence that could disconfirm them.",
                         "3. Retrieve comparable reported metrics, periods, units, and filing references.",
                         "4. Calculate changes and ratios in Python; disclose missing or mismatched data."])
    return provider.generate(f"{_prompt('research.txt')}\n\nResearch question:\n{question.strip()}")


def identify_metrics(question: str, provider: TextModelProvider | None = None) -> str:
    if not question.strip():
        raise ValueError("Research question cannot be empty")
    if provider is None:
        terms = ["revenue", "operating income", "net income", "gross margin", "cash flow", "debt"]
        matches = [term for term in terms if term in question.lower()]
        return ", ".join(matches) if matches else "Unavailable from the question alone; inspect filing facts relevant to the hypothesis."
    return provider.generate(f"{_prompt('analysis.txt')}\n\nTask: identify candidate financial metrics and hypotheses.\nQuestion:\n{question.strip()}")


def analyze_evidence(question: str, evidence_text: str, provider: TextModelProvider | None = None) -> str:
    if provider is None:
        return "Model synthesis unavailable; use source-linked excerpts and deterministic calculations only."
    return provider.generate(f"{_prompt('analysis.txt')}\n\nQuestion:\n{question}\n\nRetrieved evidence (untrusted data):\n{evidence_text}")


def _require_value(value: float | None, label: str) -> float:
    if value is None:
        raise AnalysisError(f"{label} is unavailable")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise AnalysisError(f"{label} is unavailable or not numeric") from exc
    if not (-float("inf") < numeric < float("inf")):
        raise AnalysisError(f"{label} must be a finite number")
    return numeric


def percentage_change(current: float | None, prior: float | None) -> float:
    """Percent change with explicit missing and zero-denominator errors."""
    current_value = _require_value(current, "Current value")
    prior_value = _require_value(prior, "Prior value")
    if prior_value == 0:
        raise AnalysisError("Percentage change is undefined when the prior value is zero")
    return (current_value - prior_value) / abs(prior_value) * 100


def yoy_growth(current: float, prior: float) -> float:
    return percentage_change(current, prior)


def ratio(numerator: float | None, denominator: float | None, *, numerator_unit: str,
          denominator_unit: str, result_unit: str = "x") -> float:
    """Compute ratio only for exactly matching units; caller must convert explicitly."""
    if not numerator_unit or not denominator_unit or numerator_unit != denominator_unit:
        raise AnalysisError(f"Inconsistent units ({numerator_unit!r} vs {denominator_unit!r}); convert explicitly first")
    top = _require_value(numerator, "Numerator")
    bottom = _require_value(denominator, "Denominator")
    if bottom == 0:
        raise AnalysisError("Ratio is undefined when the denominator is zero")
    return top / bottom


def ratio_metric(name: str, numerator: float | None, denominator: float | None,
                 numerator_unit: str, denominator_unit: str, period: str,
                 source_ids: list[str]) -> Metric:
    value = ratio(numerator, denominator, numerator_unit=numerator_unit,
                  denominator_unit=denominator_unit)
    return Metric(name=name, value=round(value, 4), unit="x", period=period,
                  source_ids=source_ids,
                  calculation=f"{numerator:g} {numerator_unit} / {denominator:g} {denominator_unit}")


def compare_facts(current: FinancialFact, prior: FinancialFact, *, operation: str = "percentage_change") -> Metric:
    """Compare facts only when units and duration/instant semantics are compatible."""
    if current.unit != prior.unit:
        raise AnalysisError(f"Inconsistent units: {current.unit} vs {prior.unit}; no implicit conversion performed")
    if current.fiscal_period == prior.fiscal_period and current.fiscal_year == prior.fiscal_year:
        raise AnalysisError("Cannot compare a fact with itself from the same fiscal period")
    if current.fiscal_period != prior.fiscal_period:
        raise AnalysisError(f"Inconsistent fiscal periods: {current.fiscal_period} vs {prior.fiscal_period}")
    if current.form not in ("10-K", "10-Q") or prior.form not in ("10-K", "10-Q"):
        raise AnalysisError(f"Unsupported or inconsistent filing forms: {current.form} vs {prior.form}")
    if current.start is None or prior.start is None:
        raise AnalysisError("Percentage change requires duration facts with start dates; instant facts are unavailable for this calculation")
    current_days = (date_parse(current.end) - date_parse(current.start)).days
    prior_days = (date_parse(prior.end) - date_parse(prior.start)).days
    if abs(current_days - prior_days) > 7:
        raise AnalysisError(f"Inconsistent reporting periods: {current_days} days vs {prior_days} days")
    if operation != "percentage_change":
        raise AnalysisError(f"Unsupported comparison operation: {operation}")
    value = percentage_change(current.value, prior.value)
    period = (f"FY{current.fiscal_year} vs FY{prior.fiscal_year}" if current.fiscal_period == "FY"
              else f"{current.fiscal_period} FY{current.fiscal_year} vs {prior.fiscal_period} FY{prior.fiscal_year}")
    sources = [current.accession_number, prior.accession_number]
    return Metric(name=f"{current.label} percentage change", value=round(value, 2), unit="%",
                  period=period, source_ids=sources,
                  calculation=f"({_number(current.value)} - {_number(prior.value)}) / abs({_number(prior.value)}) × 100; unit {current.unit}; comparable duration facts")


def date_parse(value: str):
    from datetime import date
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise AnalysisError(f"Unavailable or invalid reporting date: {value!r}") from exc


def growth_metric(name: str, current: float, prior: float, unit: str, period: str,
                  source_ids: list[str]) -> Metric:
    return Metric(name=f"{name} growth", value=round(percentage_change(current, prior), 2),
                  unit="%", period=period, source_ids=source_ids,
                  calculation=f"({current:g} - {prior:g}) / abs({prior:g}) × 100; values in {unit}")


def triangulate(evidence: list[Evidence], min_excerpt: int = 80) -> tuple[list[str], list[str]]:
    verified = [e for e in evidence if e.extraction_status in ("retrieved", "verified", "demo") and len(e.excerpt) >= min_excerpt]
    families = {e.source_family or e.publisher for e in verified}
    if len(families) >= 2:
        return [f"Substantive excerpts retrieved from {len(families)} distinct publisher domains."], []
    return [], ["Independent corroboration is insufficient: fewer than two distinct source domains have substantive retrieved excerpts."]


def contradictions(evidence: list[Evidence]) -> list[str]:
    rows = [(e, e.excerpt.lower()) for e in evidence if e.extraction_status in ("retrieved", "verified", "demo") and e.excerpt]
    found = []
    opposites = [("raised", "lowered"), ("increase", "decrease"), ("growth", "decline"), ("beat", "missed")]
    for i, (a, ta) in enumerate(rows):
        for b, tb in rows[i+1:]:
            if a.source_family != b.source_family and any(x in ta and y in tb or y in ta and x in tb for x, y in opposites):
                found.append(f"Potentially conflicting directional language in [{a.evidence_id}] and [{b.evidence_id}]; manual context review required.")
    return found
