"""Regression tests for Semantic Scholar paper-identifier URL handling."""

import asyncio

import pytest

import semantic_scholar_client as s2


class _Response:
    status_code = 200
    url = "https://api.semanticscholar.org/test"

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@pytest.mark.parametrize(
    ("paper_id", "encoded"),
    [
        ("DOI:10.1038/nature14539", "DOI:10.1038%2Fnature14539"),
        ("PMID:12345678", "PMID:12345678"),
    ],
)
def test_quote_paper_id_preserves_namespace_colon(paper_id, encoded):
    assert s2._quote_paper_id(paper_id) == encoded


def test_sync_paper_endpoints_preserve_prefix_colon(monkeypatch, tmp_db_dir):
    urls = []

    def fake_get(url, **kwargs):
        urls.append(url)
        if "/recommendations/" in url:
            return _Response({"recommendedPapers": []})
        return _Response({"data": []})

    monkeypatch.setattr(s2.http_client, "get", fake_get)
    paper_id = "DOI:10.1038/nature14539"

    s2.get_paper_details(paper_id)
    s2.get_paper_citations(paper_id)
    s2.get_paper_references(paper_id)
    s2.get_recommended_papers(paper_id)

    encoded = "DOI:10.1038%2Fnature14539"
    assert urls == [
        f"{s2.S2_API_BASE}/paper/{encoded}",
        f"{s2.S2_API_BASE}/paper/{encoded}/citations",
        f"{s2.S2_API_BASE}/paper/{encoded}/references",
        "https://api.semanticscholar.org/recommendations/v1/papers/forpaper/"
        f"{encoded}",
    ]


def test_async_related_endpoint_preserves_prefix_colon(monkeypatch, tmp_db_dir):
    urls = []

    async def fake_async_get(url, **kwargs):
        urls.append(url)
        return _Response({"data": []})

    monkeypatch.setattr(s2.http_client, "async_get", fake_async_get)

    result = asyncio.run(
        s2.async_get_paper_citations("PMID:12345678", num_results=20)
    )

    assert result == []
    assert urls == [f"{s2.S2_API_BASE}/paper/PMID:12345678/citations"]


class _StatusResponse(_Response):
    def __init__(self, status_code, payload=None):
        super().__init__(payload)
        self.status_code = status_code


@pytest.fixture
def rejected_key_env(monkeypatch):
    monkeypatch.setenv("S2_API_KEY", "revoked-key")
    monkeypatch.setattr(s2, "_key_rejected", False)


def test_batch_retries_without_key_after_403(monkeypatch, rejected_key_env):
    sent_keys = []

    def fake_post(url, headers, **kwargs):
        sent_keys.append(headers.get("x-api-key"))
        if "x-api-key" in headers:
            return _StatusResponse(403)
        return _StatusResponse(200, [{"paperId": "abc", "title": "T"}])

    monkeypatch.setattr(s2.http_client, "post", fake_post)

    result = s2.batch_get_papers(["DOI:10.1/x"])

    assert result[0]["title"] == "T"
    assert sent_keys == ["revoked-key", None]
    assert s2._headers().get("x-api-key") is None


def test_rejected_key_is_not_resent(monkeypatch, rejected_key_env, tmp_db_dir):
    sent_keys = []

    def fake_get(url, headers, **kwargs):
        sent_keys.append(headers.get("x-api-key"))
        if "x-api-key" in headers:
            return _StatusResponse(403)
        return _StatusResponse(200, {"data": []})

    monkeypatch.setattr(s2.http_client, "get", fake_get)

    s2.get_paper_citations("PMID:1")
    s2.get_paper_references("PMID:1")

    assert sent_keys == ["revoked-key", None, None]


def test_async_get_retries_without_key_after_403(monkeypatch, rejected_key_env):
    sent_keys = []

    async def fake_async_get(url, headers, **kwargs):
        sent_keys.append(headers.get("x-api-key"))
        if "x-api-key" in headers:
            return _StatusResponse(403)
        return _StatusResponse(200, {"data": []})

    monkeypatch.setattr(s2.http_client, "async_get", fake_async_get)

    assert asyncio.run(s2.async_get_paper_citations("PMID:1")) == []
    assert sent_keys == ["revoked-key", None]


def test_keyless_403_is_still_raised(monkeypatch, tmp_db_dir):
    monkeypatch.delenv("S2_API_KEY", raising=False)
    monkeypatch.setattr(s2, "_key_rejected", False)
    calls = []

    def fake_get(url, headers, **kwargs):
        calls.append(headers)
        return _StatusResponse(403)

    monkeypatch.setattr(s2.http_client, "get", fake_get)

    with pytest.raises(s2.http_client.requests.HTTPError, match="HTTP 403"):
        s2.get_paper_details("PMID:1")
    assert len(calls) == 1
