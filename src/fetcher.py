"""Bounded, best-effort retrieval of publicly accessible HTML pages."""
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from config import MAX_PAGE_CHARS, REQUEST_TIMEOUT
from src.search import is_advertising_redirect

HEADERS = {"User-Agent": "SignalXResearch/1.0 (public research; contact@example.com)"}


def fetch_page(url: str, timeout: int = REQUEST_TIMEOUT, max_chars: int = MAX_PAGE_CHARS) -> dict:
    retrieved_at = datetime.now(timezone.utc)
    response = None
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Only valid HTTPS URLs are retrieved")
        response = requests.get(url, headers=HEADERS, timeout=timeout,
                                allow_redirects=True, stream=True)
        response.raise_for_status()
        final_url = getattr(response, "url", None) or url
        if not isinstance(final_url, str) or not final_url.startswith(("https://", "http://")):
            final_url = url
        if is_advertising_redirect(final_url):
            return {"status": "inaccessible", "text": "", "title": "", "published_at": None,
                    "canonical_url": None, "retrieved_at": retrieved_at,
                    "error": "Advertising redirect rejected; destination was not used as evidence"}
        ctype = response.headers.get("Content-Type", "")
        if "text/html" not in ctype.lower():
            return {"status": "inaccessible", "text": "", "title": "", "published_at": None,
                    "canonical_url": None, "retrieved_at": retrieved_at, "error": f"Unsupported content type: {ctype or 'unknown'}"}
        chunks, size = [], 0
        # Keep head metadata even when body extraction is capped.
        head_limit = max(max_chars, 8192)
        for chunk in response.iter_content(8192, decode_unicode=True):
            if not chunk:
                continue
            if isinstance(chunk, bytes):
                chunk = chunk.decode(response.encoding or "utf-8", errors="replace")
            remaining = head_limit - size
            chunks.append(chunk[:remaining]); size += min(len(chunk), remaining)
            if size >= head_limit:
                break
        soup = BeautifulSoup("".join(chunks), "html.parser")
        for node in soup(["script", "style", "noscript", "svg"]):
            node.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        canonical_url = None
        canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
        if canonical and canonical.get("href"):
            candidate = urljoin(response.url or url, canonical["href"].strip())
            canonical_parsed = urlparse(candidate)
            if canonical_parsed.scheme in ("http", "https") and canonical_parsed.hostname:
                canonical_url = candidate
        date = None
        for key in ("article:published_time", "datePublished", "pubdate", "datePublished", "date", "DC.date.issued"):
            tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
            if tag and tag.get("content"):
                date = tag["content"]; break
        text = " ".join(soup.get_text(" ", strip=True).split())[:max_chars]
        return {"status": "retrieved" if text else "unverified", "text": text,
                "title": title, "published_at": date, "canonical_url": canonical_url,
                "retrieved_at": retrieved_at, "error": None}
    except Exception as exc:
        return {"status": "inaccessible", "text": "", "title": "", "published_at": None,
                "canonical_url": None, "retrieved_at": retrieved_at, "error": str(exc)}
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
