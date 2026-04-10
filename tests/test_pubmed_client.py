"""
Tests for pubmed_client.py — PubMed/NCBI E-utilities client.
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

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
