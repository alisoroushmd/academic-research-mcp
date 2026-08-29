"""
Tests for pubmed_client.py — PubMed/NCBI E-utilities client.
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest
import requests


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pubmed_client

# ---------------------------------------------------------------------------
# Sample test data
# ---------------------------------------------------------------------------

ESEARCH_JSON = {
    "esearchresult": {
        "count": "2847",
        "retmax": "3",
        "retstart": "0",
        "idlist": ["39876543", "39654321", "39123456"],
        "webenv": "MCID_abc123webenv",
        "querykey": "1",
        "querytranslation": '"intestinal metaplasia"[MeSH] AND "deep learning"[tw]',
    }
}

EFETCH_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE PubmedArticleSet PUBLIC "-//NLM//DTD PubMedArticle, 1st January 2019//EN"
  "https://dtd.nlm.nih.gov/ncbi/pubmed/out/pubmed_190101.dtd">
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE" Owner="NLM">
      <PMID Version="1">39876543</PMID>
      <Article PubModel="Print-Electronic">
        <Journal>
          <ISSN IssnType="Electronic">1097-6779</ISSN>
          <JournalIssue CitedMedium="Internet">
            <Volume>99</Volume>
            <Issue>3</Issue>
            <PubDate>
              <Year>2024</Year>
              <Month>Mar</Month>
            </PubDate>
          </JournalIssue>
          <Title>Gastrointestinal Endoscopy</Title>
        </Journal>
        <ArticleTitle>Deep learning for gastric intestinal metaplasia detection.</ArticleTitle>
        <Pagination>
          <MedlinePgn>450-458</MedlinePgn>
        </Pagination>
        <Abstract>
          <AbstractText>A study on deep learning methods for detecting gastric intestinal metaplasia.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author ValidYN="Y">
            <LastName>Soroush</LastName>
            <Initials>A</Initials>
          </Author>
          <Author ValidYN="Y">
            <LastName>Patel</LastName>
            <Initials>B</Initials>
          </Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType UI="D016428">Journal Article</PublicationType>
        </PublicationTypeList>
        <ELocationID EIdType="doi" ValidYN="Y">10.1016/j.gie.2024.001</ELocationID>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName UI="D008679" MajorTopicYN="N">Intestinal Metaplasia</DescriptorName>
        </MeshHeading>
        <MeshHeading>
          <DescriptorName UI="D000077224" MajorTopicYN="Y">Deep Learning</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">39876543</ArticleId>
        <ArticleId IdType="doi">10.1016/j.gie.2024.001</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


def _make_mock_response(json_data=None, content=None, status_code=200):
    """Build a mock requests.Response-like object."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    if json_data is not None:
        mock.json.return_value = json_data
    if content is not None:
        mock.content = content
        mock.text = content.decode("utf-8") if isinstance(content, bytes) else content
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_esearch_returns_pmids():
    """esearch() should parse count, idlist, webenv, querykey, querytranslation."""
    mock_resp = _make_mock_response(json_data=ESEARCH_JSON)

    with patch("http_client.get", return_value=mock_resp) as mock_get:
        result = pubmed_client.esearch(
            "intestinal metaplasia[MeSH] AND deep learning", max_results=100
        )

    mock_get.assert_called_once()
    assert result["pmids"] == ["39876543", "39654321", "39123456"]
    assert result["total_count"] == 2847
    assert (
        result["query_translation"]
        == '"intestinal metaplasia"[MeSH] AND "deep learning"[tw]'
    )
    assert result["webenv"] == "MCID_abc123webenv"
    assert result["query_key"] == "1"


def test_efetch_parses_xml():
    """efetch() should parse XML into standardized paper dicts with all expected fields."""
    mock_resp = _make_mock_response(content=EFETCH_XML)

    with patch("http_client.get", return_value=mock_resp):
        papers = pubmed_client.efetch(pmids=["39876543"])

    assert len(papers) == 1
    paper = papers[0]

    assert paper["pmid"] == "39876543"
    assert (
        paper["title"] == "Deep learning for gastric intestinal metaplasia detection."
    )
    assert paper["doi"] == "10.1016/j.gie.2024.001"
    assert paper["year"] == 2024
    assert paper["journal"] == "Gastrointestinal Endoscopy"
    assert paper["volume"] == "99"
    assert paper["issue"] == "3"
    assert paper["pages"] == "450-458"
    assert paper["authors"] == ["Soroush A", "Patel B"]
    assert "Intestinal Metaplasia" in paper["mesh_headings"]
    assert "Deep Learning" in paper["mesh_headings"]
    assert "Journal Article" in paper["publication_types"]
    assert paper["source"] == "pubmed"


def test_search_pubmed_end_to_end(tmp_db_dir):
    """search_pubmed() should combine esearch + efetch and return structured result."""
    mock_search_resp = _make_mock_response(json_data=ESEARCH_JSON)
    mock_fetch_resp = _make_mock_response(content=EFETCH_XML)

    # search_pubmed calls esearch then efetch; return appropriate mock per call
    call_count = 0

    def side_effect(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if "esearch" in url:
            return mock_search_resp
        return mock_fetch_resp

    with patch("http_client.get", side_effect=side_effect):
        result = pubmed_client.search_pubmed(
            "intestinal metaplasia[MeSH] AND deep learning", max_results=10
        )

    assert result["total_count"] == 2847
    assert (
        result["query_translation"]
        == '"intestinal metaplasia"[MeSH] AND "deep learning"[tw]'
    )
    assert isinstance(result["papers"], list)
    assert len(result["papers"]) == 1

    paper = result["papers"][0]
    assert paper["pmid"] == "39876543"
    assert (
        paper["title"] == "Deep learning for gastric intestinal metaplasia detection."
    )
    assert paper["doi"] == "10.1016/j.gie.2024.001"
    assert paper["year"] == 2024


# ---------------------------------------------------------------------------
# Error sanitization — the api_key rides in the URL query string, and the
# server returns str(exception) to the MCP client, so HTTP error messages
# must never contain the query string.
# ---------------------------------------------------------------------------

_URL_WITH_KEY = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&api_key=SECRET-KEY-123&term=cancer"
)


def test_esearch_http_error_redacts_query_string():
    """esearch() errors must not leak the NCBI api_key or any query params."""
    mock_resp = _make_mock_response(json_data={}, status_code=500)
    mock_resp.url = _URL_WITH_KEY

    with patch("http_client.get", return_value=mock_resp):
        with pytest.raises(requests.HTTPError) as exc_info:
            pubmed_client.esearch("cancer")

    msg = str(exc_info.value)
    assert "SECRET-KEY-123" not in msg
    assert "api_key" not in msg
    assert "?" not in msg
    assert "500" in msg


def test_efetch_http_error_redacts_query_string():
    """efetch() errors must not leak the NCBI api_key or any query params."""
    mock_resp = _make_mock_response(content=b"", status_code=403)
    mock_resp.url = _URL_WITH_KEY.replace("esearch", "efetch")

    with patch("http_client.get", return_value=mock_resp):
        with pytest.raises(requests.HTTPError) as exc_info:
            pubmed_client.efetch(pmids=["39876543"])

    msg = str(exc_info.value)
    assert "SECRET-KEY-123" not in msg
    assert "api_key" not in msg
    assert "403" in msg


# ---------------------------------------------------------------------------
# Pagination — results are capped at one EFetch batch per call; callers page
# with offset instead of receiving the entire result set in one response.
# ---------------------------------------------------------------------------


def _paged_side_effect(esearch_json, calls):
    """Record (url, params) per request; serve canned ESearch/EFetch bodies."""

    def side_effect(url, **kwargs):
        calls.append((url, kwargs.get("params", {})))
        if "esearch" in url:
            return _make_mock_response(json_data=esearch_json)
        return _make_mock_response(content=EFETCH_XML)

    return side_effect


def test_search_pubmed_caps_results_at_one_page(tmp_db_dir):
    """max_results clamps to 200 and exactly one EFetch batch is issued."""
    esearch_json = {
        "esearchresult": {
            "count": "10000",
            "idlist": [str(i) for i in range(200)],
            "webenv": "MCID_abc123webenv",
            "querykey": "1",
            "querytranslation": "cancer",
        }
    }
    calls = []
    with patch("http_client.get", side_effect=_paged_side_effect(esearch_json, calls)):
        result = pubmed_client.search_pubmed("cancer", max_results=10000)

    esearch_calls = [c for c in calls if "esearch" in c[0]]
    efetch_calls = [c for c in calls if "efetch" in c[0]]
    assert len(esearch_calls) == 1
    assert esearch_calls[0][1]["retmax"] == 200
    assert len(efetch_calls) == 1  # no batch loop fetching all 10000 records
    assert efetch_calls[0][1]["retmax"] == 200
    assert result["total_count"] == 10000
    assert result["offset"] == 0
    assert result["has_more"] is True


def test_search_pubmed_offset_requests_later_page(tmp_db_dir):
    """offset flows to ESearch retstart and EFetch retstart."""
    calls = []
    with patch("http_client.get", side_effect=_paged_side_effect(ESEARCH_JSON, calls)):
        result = pubmed_client.search_pubmed("cancer", max_results=200, offset=200)

    esearch_calls = [c for c in calls if "esearch" in c[0]]
    efetch_calls = [c for c in calls if "efetch" in c[0]]
    assert esearch_calls[0][1]["retstart"] == 200
    assert efetch_calls[0][1]["retstart"] == 200
    assert result["offset"] == 200
    assert result["returned"] == 1  # EFETCH_XML contains one article
    assert result["has_more"] is True  # 200 + 1 < 2847


def test_search_pubmed_last_page_has_more_false(tmp_db_dir):
    """When the page reaches total_count, has_more is False."""
    esearch_json = {
        "esearchresult": {
            "count": "1",
            "idlist": ["39876543"],
            "webenv": "MCID_abc123webenv",
            "querykey": "1",
            "querytranslation": "cancer",
        }
    }
    calls = []
    with patch("http_client.get", side_effect=_paged_side_effect(esearch_json, calls)):
        result = pubmed_client.search_pubmed("cancer")

    assert result["returned"] == 1
    assert result["has_more"] is False


def test_search_pubmed_cache_is_keyed_by_offset(tmp_db_dir):
    """Different offsets must produce different cache entries, not collide."""
    calls = []
    with patch("http_client.get", side_effect=_paged_side_effect(ESEARCH_JSON, calls)):
        pubmed_client.search_pubmed("cancer", max_results=200, offset=0)
        pubmed_client.search_pubmed("cancer", max_results=200, offset=200)

    esearch_calls = [c for c in calls if "esearch" in c[0]]
    assert len(esearch_calls) == 2  # second offset was a cache miss, as it must be
