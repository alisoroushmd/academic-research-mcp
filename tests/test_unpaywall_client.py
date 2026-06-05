"""
Tests for unpaywall_client.py — open access PDF resolution and, in particular,
its *diagnosability*: a config/email problem, an invalid DOI, and a genuine
"not in Unpaywall" miss must each produce a distinct, self-explaining result so
the failure mode can be troubleshooted without guessing.
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unpaywall_client

GOOD_EMAIL = "researcher@university.edu"


def _resp(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


# ---------------------------------------------------------------------------
# Contact-email validation (the original misdiagnosis root cause)
# ---------------------------------------------------------------------------

def test_no_email_is_a_config_error_not_a_miss():
    with patch.object(unpaywall_client.http_client, "get_env", return_value=""):
        result = unpaywall_client.get_paper_pdf("10.1038/s41591-023-02437-x")
    assert result["error_type"] == "config"
    assert result.get("config_issue") is True
    assert "OPENALEX_EMAIL" in result["error"]


def test_placeholder_email_is_rejected_as_config_error():
    for placeholder in (
        "your-email@example.com",
        "you@example.org",
        "changeme@gmail.com",
        "placeholder@domain.com",
    ):
        with patch.object(unpaywall_client.http_client, "get_env", return_value=placeholder):
            result = unpaywall_client.get_paper_pdf("10.1038/s41591-023-02437-x")
        assert result["error_type"] == "config", f"{placeholder!r} should be flagged"
        assert result.get("config_issue") is True
        assert placeholder in result["error"]


def test_malformed_email_is_rejected_as_config_error():
    with patch.object(unpaywall_client.http_client, "get_env", return_value="not-an-email"):
        result = unpaywall_client.get_paper_pdf("10.1038/s41591-023-02437-x")
    assert result["error_type"] == "config"
    assert result.get("config_issue") is True


def test_real_email_is_accepted():
    email_problem, _ = unpaywall_client._validate_contact_email(GOOD_EMAIL)
    assert email_problem == ""


# ---------------------------------------------------------------------------
# Invalid / empty DOI must be distinct from a real "not found"
# ---------------------------------------------------------------------------

def test_empty_doi_is_invalid_doi_not_not_found():
    result = unpaywall_client.get_paper_pdf("")
    assert result["error_type"] == "invalid_doi"
    assert result["found"] is False
    # The message must point the caller at how to obtain a real DOI.
    assert "find_paper" in result["error"] or "smart_search" in result["error"]


def test_garbage_doi_is_invalid_doi():
    result = unpaywall_client.get_paper_pdf("not-a-doi")
    assert result["error_type"] == "invalid_doi"


# ---------------------------------------------------------------------------
# Genuine 404 from Unpaywall must read as "not indexed", not a config problem
# ---------------------------------------------------------------------------

def test_404_is_not_in_unpaywall():
    with patch.object(unpaywall_client.http_client, "get_env", return_value=GOOD_EMAIL), \
         patch.object(unpaywall_client.http_client, "get", return_value=_resp(404)):
        result = unpaywall_client.get_paper_pdf("10.9999/does-not-exist")
    assert result["error_type"] == "not_in_unpaywall"
    assert result["found"] is False
    assert "config_issue" not in result


# ---------------------------------------------------------------------------
# Batch mode must PRESERVE the error distinction (the silent-flatten bug)
# ---------------------------------------------------------------------------

def test_batch_propagates_config_error_per_item():
    with patch.object(unpaywall_client.http_client, "get_env", return_value=""):
        results = unpaywall_client.batch_check_oa(
            ["10.1038/s41591-023-02437-x", "10.1016/j.gie.2023.06.056"]
        )
    assert len(results) == 2
    for item in results:
        # A config problem must NOT masquerade as is_oa=False with no explanation.
        assert item["error_type"] == "config"
        assert item.get("config_issue") is True


def test_batch_marks_empty_doi_as_invalid_doi():
    with patch.object(unpaywall_client.http_client, "get_env", return_value=GOOD_EMAIL):
        results = unpaywall_client.batch_check_oa(["", "  "])
    for item in results:
        assert item["error_type"] == "invalid_doi"


def test_batch_returns_clean_hit_for_oa_paper():
    oa_json = {
        "doi": "10.1038/x",
        "is_oa": True,
        "oa_status": "gold",
        "best_oa_location": {
            "url_for_pdf": "https://example-journal.test/x.pdf",
            "host_type": "publisher",
            "version": "publishedVersion",
        },
        "oa_locations": [],
    }
    with patch.object(unpaywall_client.http_client, "get_env", return_value=GOOD_EMAIL), \
         patch.object(unpaywall_client.http_client, "get", return_value=_resp(200, oa_json)):
        results = unpaywall_client.batch_check_oa(["10.1038/x"])
    item = results[0]
    assert item["is_oa"] is True
    assert item["pdf_url"] == "https://example-journal.test/x.pdf"
    assert "error_type" not in item
