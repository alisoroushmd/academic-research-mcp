"""
Unpaywall API client — legal open access PDF resolver.

Unpaywall (https://unpaywall.org) is the authoritative source for legal open access
copies of academic papers. It indexes 30M+ free-to-read articles from publisher sites,
PubMed Central, institutional repositories, and preprint servers.

No API key required — just an email address. Uses the same OPENALEX_EMAIL env var.
Rate limit: 100,000 requests/day.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List
import http_client

UNPAYWALL_BASE = "https://api.unpaywall.org/v2"

# Substrings that mark an email as a stand-in rather than a real contact address.
# Unpaywall ignores/blocks placeholder addresses, so passing one looks exactly
# like a global outage ("nothing resolves") unless we flag it up front.
_PLACEHOLDER_EMAIL_FRAGMENTS = (
    "example.com",
    "example.org",
    "example.net",
    "your-email",
    "your_email",
    "youremail",
    "yourname",
    "changeme",
    "change-me",
    "placeholder",
    "noreply",
    "no-reply",
    "test@test",
    "user@domain",
    "email@email",
    "foo@bar",
)


def _validate_contact_email(email: str) -> tuple[str, str]:
    """
    Classify a contact email for Unpaywall/OpenAlex use.

    Returns:
        (problem, email) where problem is "" when the address is usable, or one
        of "no_email" / "malformed_email" / "placeholder_email" otherwise. The
        normalized email is returned so callers can echo it in diagnostics.
    """
    email = (email or "").strip()
    if not email:
        return "no_email", email
    low = email.lower()
    # Minimal shape check: local@domain.tld
    if "@" not in low or "." not in low.rsplit("@", 1)[-1]:
        return "malformed_email", email
    if any(fragment in low for fragment in _PLACEHOLDER_EMAIL_FRAGMENTS):
        return "placeholder_email", email
    return "", email


def _resolve_contact_email() -> tuple[str, str]:
    """Read OPENALEX_EMAIL (fallback CROSSREF_EMAIL) and validate it.

    Returns (problem, email); see _validate_contact_email.
    """
    raw = http_client.get_env("OPENALEX_EMAIL", http_client.get_env("CROSSREF_EMAIL"))
    return _validate_contact_email(raw)


_EMAIL_PROBLEM_MESSAGES = {
    "no_email": (
        "OPENALEX_EMAIL is not set, so Unpaywall open-access resolution is "
        "disabled. Set OPENALEX_EMAIL (or CROSSREF_EMAIL) to a real contact "
        "email in the MCP server environment, then restart the server."
    ),
    "malformed_email": (
        "OPENALEX_EMAIL ({email!r}) is not a valid email address. Unpaywall "
        "requires a real contact email; set OPENALEX_EMAIL to a working address "
        "and restart the server."
    ),
    "placeholder_email": (
        "OPENALEX_EMAIL ({email!r}) looks like a placeholder. Unpaywall "
        "ignores/blocks placeholder addresses, which makes every lookup fail as "
        "if no paper were open access. Set OPENALEX_EMAIL to your real contact "
        "email and restart the server."
    ),
}


def _config_error(problem: str, email: str) -> Dict[str, Any]:
    """Build a self-explaining config error for an email problem."""
    return {
        "error": _EMAIL_PROBLEM_MESSAGES[problem].format(email=email),
        "error_type": "config",
        "config_issue": True,
        "found": False,
        "pdf_url": None,
    }


def get_paper_pdf(doi: str) -> Dict[str, Any]:
    """
    Resolve the best available legal PDF for a paper by DOI.

    Walks through a resolution chain:
    1. Unpaywall (publisher OA, green OA, bronze OA, hybrid)
    2. PubMed Central link (for NIH-funded work)
    3. Preprint version (arXiv, medRxiv, bioRxiv)
    4. Publisher landing page (if no OA version found)

    Parameters:
        doi: DOI string (e.g., "10.1038/s41591-023-02437-x").

    Returns:
        Dict with pdf_url, source, oa_status, and all available locations.
    """
    doi = _clean_doi(doi)
    if not doi:
        return {
            "error": (
                "Invalid or empty DOI. open_access resolves PDFs by DOI only; "
                "resolve a real DOI first via find_paper or smart_search, then "
                "pass that DOI here."
            ),
            "error_type": "invalid_doi",
            "found": False,
            "pdf_url": None,
        }

    problem, email = _resolve_contact_email()
    if problem:
        return _config_error(problem, email)

    url = f"{UNPAYWALL_BASE}/{doi}"
    params = {"email": email}

    try:
        resp = http_client.get(url, params=params)
    except Exception as e:
        return {"error": f"Unpaywall request failed: {str(e)}"}

    if resp.status_code == 404:
        return {
            "doi": doi,
            "found": False,
            "is_oa": False,
            "pdf_url": None,
            "error_type": "not_in_unpaywall",
            "message": (
                "DOI not indexed by Unpaywall (the DOI and contact email are "
                "valid; this paper simply is not in Unpaywall's OA index). Try "
                "the publisher page."
            ),
            "publisher_url": f"https://doi.org/{doi}",
        }

    if resp.status_code == 422:
        # Unpaywall returns 422 specifically for a bad/invalid email parameter.
        return _config_error("malformed_email", email)

    if resp.status_code != 200:
        return {
            "error": f"Unpaywall API error: {resp.status_code}",
            "error_type": "api_error",
            "found": False,
            "pdf_url": None,
        }

    data = resp.json()

    # Best OA location (Unpaywall's own ranking)
    best_oa = data.get("best_oa_location", {}) or {}
    best_pdf = best_oa.get("url_for_pdf", "")
    best_landing = best_oa.get("url_for_landing_page", "")

    # All OA locations
    all_locations = []
    for loc in (data.get("oa_locations", []) or []):
        location = {
            "url": loc.get("url_for_pdf") or loc.get("url_for_landing_page", ""),
            "pdf_url": loc.get("url_for_pdf", ""),
            "landing_page": loc.get("url_for_landing_page", ""),
            "source": loc.get("host_type", ""),
            "repository": loc.get("repository_institution", ""),
            "version": loc.get("version", ""),
            "license": loc.get("license", ""),
            "is_pdf": bool(loc.get("url_for_pdf")),
        }
        all_locations.append(location)

    # Categorize sources
    pmc_url = None
    preprint_url = None
    repository_url = None
    publisher_pdf = None

    for loc in all_locations:
        url_str = loc.get("url", "")
        if "ncbi.nlm.nih.gov/pmc" in url_str or "europepmc.org" in url_str:
            pmc_url = loc.get("pdf_url") or url_str
        elif any(s in url_str for s in ["arxiv.org", "medrxiv.org", "biorxiv.org"]):
            preprint_url = loc.get("pdf_url") or url_str
        elif loc.get("source") == "repository":
            repository_url = loc.get("pdf_url") or url_str
        elif loc.get("source") == "publisher" and loc.get("is_pdf"):
            publisher_pdf = loc.get("pdf_url")

    # Build resolution chain result
    result = {
        "doi": doi,
        "title": data.get("title", ""),
        "found": True,
        "is_oa": data.get("is_oa", False),
        "oa_status": data.get("oa_status", "closed"),
        "journal": data.get("journal_name", ""),
        "publisher": data.get("publisher", ""),
        "year": data.get("year"),
        "pdf_url": best_pdf or None,
        "landing_page": best_landing or f"https://doi.org/{doi}",
        "source": best_oa.get("host_type", "none"),
        "version": best_oa.get("version", ""),
        "license": best_oa.get("license", ""),
        "pmc_url": pmc_url,
        "preprint_url": preprint_url,
        "repository_url": repository_url,
        "publisher_pdf": publisher_pdf,
        "all_locations_count": len(all_locations),
        "all_locations": all_locations,
    }

    # Add human-readable message
    if best_pdf:
        result["message"] = f"PDF available ({result['source']}, {result['version']})"
    elif pmc_url:
        result["message"] = "Available via PubMed Central"
        result["pdf_url"] = pmc_url
    elif preprint_url:
        result["message"] = "Preprint version available (may differ from published)"
        result["pdf_url"] = preprint_url
    elif repository_url:
        result["message"] = "Available via institutional repository"
        result["pdf_url"] = repository_url
    else:
        result["message"] = (
            "No open access version found. Check institutional access "
            f"at https://doi.org/{doi}"
        )

    return result


def batch_check_oa(dois: List[str]) -> List[Dict[str, Any]]:
    """
    Check open access status for multiple DOIs concurrently.

    Parameters:
        dois: List of DOI strings (max 50 recommended per batch).

    Returns:
        List of dicts with doi, is_oa, pdf_url, and source for each.
        Order matches the input list.
    """
    def _check_single(idx_doi):
        idx, raw_doi = idx_doi
        doi = _clean_doi(raw_doi)
        if not doi:
            return idx, {
                "doi": raw_doi,
                "is_oa": False,
                "pdf_url": None,
                "error": (
                    "Invalid or empty DOI. Resolve a real DOI via find_paper or "
                    "smart_search before checking open access."
                ),
                "error_type": "invalid_doi",
            }
        try:
            result = get_paper_pdf(doi)
            # Preserve diagnostic errors (config / API / not-indexed) instead of
            # flattening them into a silent is_oa=False, which is what made a
            # config problem look like a global "nothing is open access" outage.
            if result.get("error"):
                item = {
                    "doi": doi,
                    "is_oa": False,
                    "pdf_url": None,
                    "error": result["error"],
                    "error_type": result.get("error_type", "error"),
                }
                if result.get("config_issue"):
                    item["config_issue"] = True
                return idx, item
            return idx, {
                "doi": doi,
                "is_oa": result.get("is_oa", False),
                "pdf_url": result.get("pdf_url"),
                "source": result.get("source", "none"),
                "found": result.get("found", True),
                "message": result.get("message", ""),
            }
        except Exception as e:
            return idx, {"doi": doi, "error": str(e), "error_type": "exception"}

    results = [None] * len(dois)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_check_single, (i, d)): i for i, d in enumerate(dois)}
        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result

    return results


def _clean_doi(doi: str) -> str:
    """Clean and normalize a DOI string."""
    if not doi:
        return ""
    doi = doi.strip()
    doi = doi.replace("https://doi.org/", "")
    doi = doi.replace("http://doi.org/", "")
    doi = doi.replace("DOI:", "")
    doi = doi.replace("doi:", "")
    doi = doi.strip()
    # Basic DOI validation
    if not doi.startswith("10."):
        return ""
    return doi
