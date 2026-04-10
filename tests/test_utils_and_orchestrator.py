"""
Tests for utils.title_similarity, utils.has_medical_terms, and
orchestrator._classify_identifier.
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import title_similarity, has_medical_terms
from orchestrator import _classify_identifier


# ---------------------------------------------------------------------------
# title_similarity
# ---------------------------------------------------------------------------


class TestTitleSimilarity:
    def test_exact_match(self):
        assert title_similarity("foo bar", "foo bar") > 0.95

    def test_completely_different(self):
        assert (
            title_similarity("quantum physics entanglement", "recipe chocolate cake")
            < 0.2
        )

    def test_partial_overlap(self):
        score = title_similarity(
            "deep learning endoscopy Barrett",
            "Deep learning for Barrett's oesophagus detection in endoscopy",
        )
        assert score > 0.5

    def test_empty_strings(self):
        assert title_similarity("", "some title") == 0.0
        assert title_similarity("some query", "") == 0.0
        assert title_similarity("", "") == 0.0

    def test_generic_words_downweighted(self):
        # Generic words ("the", "of") get 0.5 weight; distinctive words get 1.0.
        # Word score component should reflect this weighting.
        score = title_similarity("gastric metaplasia", "gastric metaplasia screening")
        # Both distinctive words match — should score high
        assert score > 0.7
        # A query of only generic words matching shouldn't score as high in word component
        score_generic = title_similarity("the method", "the method for analysis")
        score_distinct = title_similarity(
            "gastric adenocarcinoma", "gastric adenocarcinoma risk"
        )
        # Distinctive match should beat generic match (word score component is higher)
        assert score_distinct >= score_generic

    def test_case_insensitive(self):
        s1 = title_similarity("Barrett Esophagus", "barrett esophagus")
        s2 = title_similarity("barrett esophagus", "barrett esophagus")
        assert abs(s1 - s2) < 0.01


# ---------------------------------------------------------------------------
# has_medical_terms
# ---------------------------------------------------------------------------


class TestHasMedicalTerms:
    def test_medical_query(self):
        assert has_medical_terms("gastric cancer screening endoscopy")

    def test_non_medical_query(self):
        assert not has_medical_terms("transformer architecture attention mechanism")

    def test_mixed_query(self):
        assert has_medical_terms("deep learning for colonoscopy polyp detection")

    def test_empty(self):
        assert not has_medical_terms("")


# ---------------------------------------------------------------------------
# _classify_identifier
# ---------------------------------------------------------------------------


class TestClassifyIdentifier:
    # DOIs
    def test_raw_doi(self):
        assert _classify_identifier("10.1038/s41591-023-02437-x") == (
            "doi",
            "10.1038/s41591-023-02437-x",
        )

    def test_doi_with_prefix(self):
        assert _classify_identifier("DOI:10.1038/nature12373") == (
            "doi",
            "10.1038/nature12373",
        )

    def test_doi_url(self):
        t, v = _classify_identifier("https://doi.org/10.1038/nature12373")
        assert t == "doi"
        assert v == "10.1038/nature12373"

    # PMIDs
    def test_raw_pmid(self):
        assert _classify_identifier("37890456") == ("pmid", "37890456")

    def test_pmid_with_prefix(self):
        assert _classify_identifier("PMID:37890456") == ("pmid", "37890456")

    def test_pubmed_url(self):
        t, v = _classify_identifier("https://pubmed.ncbi.nlm.nih.gov/37890456")
        assert t == "pmid"
        assert v == "37890456"

    # arXiv
    def test_raw_arxiv(self):
        assert _classify_identifier("2312.00567") == ("arxiv", "2312.00567")

    def test_arxiv_with_version(self):
        assert _classify_identifier("2312.00567v2") == ("arxiv", "2312.00567v2")

    def test_arxiv_with_prefix(self):
        assert _classify_identifier("arXiv:2312.00567") == ("arxiv", "2312.00567")

    def test_arxiv_url(self):
        t, v = _classify_identifier("https://arxiv.org/abs/2312.00567")
        assert t == "arxiv"
        assert v == "2312.00567"

    # medRxiv/bioRxiv
    def test_medrxiv_doi(self):
        assert _classify_identifier("10.1101/2024.01.15.24301234") == (
            "medrxiv_doi",
            "10.1101/2024.01.15.24301234",
        )

    def test_medrxiv_url(self):
        t, v = _classify_identifier(
            "https://www.medrxiv.org/content/10.1101/2024.01.15.24301234v1"
        )
        assert t == "medrxiv_doi"
        assert "10.1101" in v

    def test_biorxiv_url(self):
        t, v = _classify_identifier(
            "https://www.biorxiv.org/content/10.1101/2024.02.20.581234v1"
        )
        assert t == "medrxiv_doi"
        assert "10.1101" in v

    # Semantic Scholar
    def test_s2_hex_id(self):
        hex_id = "a" * 40
        assert _classify_identifier(hex_id) == ("s2", hex_id)

    def test_s2_url(self):
        t, v = _classify_identifier("https://www.semanticscholar.org/paper/abc123")
        assert t == "s2"
        assert v == "abc123"

    # Title fallback
    def test_title_string(self):
        assert _classify_identifier("Real-time use of AI in Barrett's oesophagus") == (
            "title",
            "Real-time use of AI in Barrett's oesophagus",
        )

    def test_short_number_not_pmid(self):
        # Only 5 digits — below PMID range (6-9 digits)
        t, _ = _classify_identifier("12345")
        assert t == "title"

    def test_long_number_not_pmid(self):
        # 10 digits — above PMID range
        t, _ = _classify_identifier("1234567890")
        assert t == "title"
