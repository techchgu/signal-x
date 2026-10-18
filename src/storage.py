"""Simple append-only JSON research history."""
import json
from pathlib import Path
from src.schemas import ResearchResult


def save_result(result: ResearchResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            rows = [row for row in loaded if isinstance(row, dict)] if isinstance(loaded, list) else []
        except (json.JSONDecodeError, OSError):
            rows = []
    record = result.model_dump(mode="json")
    # Re-saving the same in-memory result updates it instead of duplicating it.
    matching = next((i for i, row in enumerate(rows) if row.get("created_at") == record.get("created_at")), None)
    if matching is None:
        rows.append(record)
    else:
        rows[matching] = record
    path.write_text(json.dumps(rows[-100:], indent=2, ensure_ascii=False), encoding="utf-8")


def load_results(path: Path, limit: int = 100) -> list[ResearchResult]:
    """Load valid saved results; skip corrupt records rather than breaking the UI."""
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(rows, list):
        return []
    output = []
    bounded_limit = max(0, limit)
    if bounded_limit == 0:
        return []
    for row in rows[-bounded_limit:]:
        try:
            output.append(ResearchResult.model_validate(row))
        except Exception:
            continue
    return output
