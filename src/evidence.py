"""Turn retrieved pages into bounded, source-linked excerpts."""
import hashlib
from urllib.parse import urlparse
from urllib.parse import urlsplit, urlunsplit
from src.schemas import Evidence, SearchResult, utc_now
from src.fetcher import fetch_page


def family(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return host[4:] if host.startswith("www.") else host


def _id_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def excerpt_for(text: str, question: str, limit: int = 700) -> str:
    if not text:
        return ""
    terms = {t.lower().strip(".,?!:;()") for t in question.split() if len(t) > 3}
    sentences = text.replace("? ", "?\n").replace(". ", ".\n").replace("! ", "!\n").splitlines()
    scored = sorted(enumerate(sentences), key=lambda pair: sum(t in pair[1].lower() for t in terms), reverse=True)
    picked = [s.strip() for _, s in scored[:3] if s.strip()]
    return " ".join(picked)[:limit]


def retrieve(result: SearchResult, question: str, page_fetcher=fetch_page,
             search_query: str | None = None) -> Evidence:
    url = str(result.url)
    try:
        page = page_fetcher(url)
    except Exception as exc:
        page = {"status": "inaccessible", "text": "", "title": "", "published_at": None,
                "canonical_url": None, "error": f"Page retrieval failed: {exc}"}
    identifier = hashlib.sha256(_id_url(url).encode()).hexdigest()[:10]
    title = page["title"] or result.title
    retrieval_status = "accessible" if page["status"] in ("retrieved", "verified") and page["text"] else "inaccessible"
    return Evidence(evidence_id=f"E{identifier}", title=title, url=url,
                    canonical_url=page.get("canonical_url"), search_query=search_query or question,
                    search_snippet=result.snippet,
                    publisher=family(url), published_at=page["published_at"],
                    excerpt=excerpt_for(page["text"], question) if page["text"] else "",
                    retrieved_at=page.get("retrieved_at") or utc_now(),
                    extraction_status=page["status"], retrieval_status=retrieval_status,
                    verification_status="not_verified" if retrieval_status == "accessible" else "unresolved",
                    source_family=family(url), error=page.get("error"))


def retrieve_many(results: list[SearchResult], question: str, limit: int = 7,
                  page_fetcher=fetch_page, search_query: str | None = None) -> list[Evidence]:
    """Fetch bounded unique source URLs; failed pages remain explicit evidence records."""
    bounded_limit = max(0, min(limit, 7))
    if bounded_limit == 0:
        return []
    evidence, seen = [], set()
    for result in results:
        url = str(result.url)
        key = _id_url(url).lower()
        if key in seen:
            continue
        seen.add(key)
        evidence.append(retrieve(result, question, page_fetcher=page_fetcher, search_query=search_query))
        if len(evidence) >= bounded_limit:
            break
    return evidence
