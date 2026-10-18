from unittest.mock import Mock, patch

from src.evidence import retrieve_many
from src.fetcher import fetch_page
from src.search import search_web, is_advertising_redirect
from src.schemas import SearchResult
from src.search import SearchError


def test_search_provider_is_replaceable_and_limited_and_deduplicated():
    calls = []
    def provider(query, limit):
        calls.append((query, limit))
        return [
            {"title": "One", "href": "https://news.example/a", "body": "first"},
            {"title": "Duplicate", "href": "https://news.example/a/", "body": "again"},
            {"title": "Two", "href": "https://other.example/b"},
            {"title": "Three", "href": "https://third.example/c"},
        ]
    result = search_web("test query", limit=2, provider=provider)
    assert calls == [("test query", 2)]
    assert [str(r.url) for r in result] == ["https://news.example/a", "https://other.example/b"]


def test_search_empty_results_and_zero_limit():
    calls = []
    assert search_web("empty", provider=lambda query, limit: []) == []
    assert search_web("skip", limit=0, provider=lambda query, limit: calls.append(query)) == []
    assert calls == []


def test_search_network_error_is_clear():
    def provider(query, limit):
        raise TimeoutError("provider timed out")
    try:
        search_web("market demand", provider=provider)
        assert False, "expected SearchError"
    except SearchError as exc:
        assert "provider timed out" in str(exc)


def test_advertising_redirects_are_rejected_without_dropping_original_urls():
    rows = [
        {"title": "Ad click", "href": "https://www.google.com/aclk?sa=l&url=https%3A%2F%2Ffake.example"},
        {"title": "Ad network", "href": "https://click.doubleclick.net/path"},
        {"title": "Original filing", "href": "https://www.sec.gov/Archives/edgar/data/1/filing.htm"},
    ]
    results = search_web("company filing", provider=lambda query, limit: rows)
    assert [str(item.url) for item in results] == [rows[-1]["href"]]
    assert is_advertising_redirect("https://ad.doubleclick.net/path")
    assert not is_advertising_redirect(rows[-1]["href"])


@patch("src.fetcher.requests.get")
def test_fetch_extracts_title_date_and_bounded_text(mock_get):
    response = Mock()
    response.headers = {"Content-Type": "text/html; charset=utf-8"}
    response.encoding = "utf-8"
    response.iter_content.return_value = [b"<html><head><title>Annual results</title><meta property='article:published_time' content='2025-03-01'></head><body><script>ignore</script><p>Revenue grew by 20 percent.</p><p>" + b"x" * 500 + b"</p></body></html>"]
    mock_get.return_value = response
    page = fetch_page("https://issuer.example/news", max_chars=100)
    assert page["status"] == "retrieved"
    assert page["title"] == "Annual results"
    assert page["published_at"] == "2025-03-01"
    assert len(page["text"]) <= 100
    assert "ignore" not in page["text"]
    assert mock_get.call_args.kwargs["timeout"] > 0
    assert page["status"] == "retrieved"


@patch("src.fetcher.requests.get")
def test_fetch_canonical_date_retrieval_time_and_invalid_urls(mock_get):
    response = Mock()
    response.url = "https://issuer.example/redirected"
    response.headers = {"Content-Type": "text/html"}
    response.encoding = "utf-8"
    response.iter_content.return_value = [b"<html><head><title>Page</title><link rel='canonical' href='/original'><meta name='date' content='2025-07-10'></head><body>Readable text.</body></html>"]
    mock_get.return_value = response
    page = fetch_page("https://issuer.example/redirected")
    assert page["canonical_url"] == "https://issuer.example/original"
    assert page["published_at"] == "2025-07-10"
    assert page["retrieved_at"].tzinfo is not None
    assert response.close.called
    for invalid in ("http://issuer.example/page", "not a url", "https://user:pass@issuer.example/"):
        assert fetch_page(invalid)["status"] == "inaccessible"
    assert mock_get.call_count == 1


def test_fetch_non_html_and_failed_http_are_inaccessible():
    with patch("src.fetcher.requests.get") as mock_get:
        response = Mock(); response.headers = {"Content-Type": "application/pdf"}
        mock_get.return_value = response
        assert fetch_page("https://issuer.example/file")["status"] == "inaccessible"
        mock_get.side_effect = TimeoutError("timed out")
        page = fetch_page("https://issuer.example/news")
        assert page["status"] == "inaccessible" and "timed out" in page["error"]


def test_fetch_rejects_redirect_to_ad_network():
    with patch("src.fetcher.requests.get") as mock_get:
        response = Mock(); response.url = "https://googleadservices.com/pagead/aclk"
        response.headers = {"Content-Type": "text/html"}
        mock_get.return_value = response
        result = fetch_page("https://issuer.example/annual-report")
    assert result["status"] == "inaccessible"
    assert "Advertising redirect rejected" in result["error"]


def test_retrieve_many_preserves_original_urls_and_failed_evidence():
    results = [
        SearchResult(title="A", url="https://a.example/story", snippet="A snippet"),
        SearchResult(title="A duplicate", url="https://a.example/story/", snippet="duplicate"),
        SearchResult(title="B", url="https://b.example/story"),
    ]
    def fake_fetch(url):
        if "b.example" in url:
            return {"status": "inaccessible", "text": "", "title": "", "published_at": None, "error": "timeout"}
        return {"status": "retrieved", "text": "The company said revenue grew 20 percent in 2025.",
                "title": "Original title", "published_at": "2025-05-01", "error": None}
    rows = retrieve_many(results, "company revenue growth", limit=2, page_fetcher=fake_fetch)
    assert len(rows) == 2
    assert rows[0].url == "https://a.example/story"
    assert rows[0].title == "Original title" and rows[0].published_at == "2025-05-01"
    assert rows[0].excerpt and rows[0].extraction_status == "retrieved"
    assert rows[0].verification_status == "not_verified"
    assert rows[0].search_query == "company revenue growth"
    assert rows[0].search_snippet == "A snippet"
    assert rows[0].retrieval_status == "accessible"
    assert rows[1].extraction_status == "inaccessible" and rows[1].error == "timeout"
    assert rows[0].evidence_id != rows[1].evidence_id


def test_retrieve_many_respects_limit():
    results = [SearchResult(title=str(i), url=f"https://site{i}.example/p") for i in range(5)]
    rows = retrieve_many(results, "question", limit=2,
                         page_fetcher=lambda url: {"status": "unverified", "text": "", "title": "", "published_at": None, "error": None})
    assert len(rows) == 2
    assert retrieve_many(results, "question", limit=0, page_fetcher=lambda url: (_ for _ in ()).throw(AssertionError("must not fetch"))) == []
