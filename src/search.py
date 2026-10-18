"""Replaceable public web search providers."""
from collections.abc import Callable, Iterable
from urllib.parse import urlparse
from src.schemas import SearchResult
from config import MAX_SEARCH_RESULTS


class SearchError(RuntimeError):
    pass


_AD_REDIRECT_HOSTS = (
    "googleadservices.com", "doubleclick.net", "adservice.google.com",
    "adnxs.com", "adform.net", "taboola.com", "outbrain.com",
)


def is_advertising_redirect(url: str) -> bool:
    """Identify known ad network URLs and common search-ad click endpoints."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
    except (TypeError, ValueError):
        return True
    if any(host == domain or host.endswith("." + domain) for domain in _AD_REDIRECT_HOSTS):
        return True
    path = parsed.path.lower()
    return (host in {"www.google.com", "google.com"} and path.startswith("/aclk")) or \
           (host in {"www.bing.com", "bing.com"} and path.startswith("/aclick"))


def _ddgs_provider(query: str, limit: int) -> Iterable[dict]:
    from ddgs import DDGS
    return DDGS().text(query, max_results=limit)


def search_web(query: str, limit: int = MAX_SEARCH_RESULTS,
               provider: Callable[[str, int], Iterable[dict]] | None = None) -> list[SearchResult]:
    """Search public web through a replaceable provider, capped to configured maximum."""
    if not query.strip():
        raise ValueError("Search query cannot be empty")
    bounded_limit = max(0, min(int(limit), MAX_SEARCH_RESULTS))
    if bounded_limit == 0:
        return []
    try:
        rows = (provider or _ddgs_provider)(query, bounded_limit)
        output, seen = [], set()
        for row in rows:
            raw_url = row.get("href") or row.get("url")
            if not raw_url or is_advertising_redirect(raw_url):
                continue
            try:
                item = SearchResult(title=row.get("title") or "Untitled", url=raw_url,
                                    snippet=row.get("body") or row.get("snippet", ""),
                                    published_at=row.get("published_at"))
            except Exception:
                continue
            key = str(item.url).rstrip("/").lower()
            if key in seen:
                continue
            seen.add(key)
            if len(output) >= bounded_limit:
                break
            output.append(item)
        return output
    except Exception as exc:
        raise SearchError(f"Public web search failed: {exc}") from exc
