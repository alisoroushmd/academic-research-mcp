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
