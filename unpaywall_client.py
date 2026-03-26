"""
Unpaywall API client — legal open access PDF resolver.

Unpaywall (https://unpaywall.org) is the authoritative source for legal open access
copies of academic papers. It indexes 30M+ free-to-read articles from publisher sites,
PubMed Central, institutional repositories, and preprint servers.

No API key required — just an email address. Uses the same OPENALEX_EMAIL env var.
Rate limit: 100,000 requests/day.
"""

import os
import re
import requests
from typing import Any, Dict, List, Optional

UNPAYWALL_BASE = "https://api.unpaywall.org/v2"
UNPAYWALL_EMAIL = os.environ.get("OPENALEX_EMAIL", os.environ.get("CROSSREF_EMAIL", ""))


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
        return {"error": "Invalid DOI format"}

    if not UNPAYWALL_EMAIL:
        return {"error": "No email configured. Set OPENALEX_EMAIL environment variable."}

    url = f"{UNPAYWALL_BASE}/{doi}"
    params = {"email": UNPAYWALL_EMAIL}

    try:
        resp = requests.get(url, params=params, timeout=15)
    except Exception as e:
        return {"error": f"Unpaywall request failed: {str(e)}"}

    if resp.status_code == 404:
        return {
            "doi": doi,
            "found": False,
            "pdf_url": None,
            "message": "DOI not found in Unpaywall. Try the publisher page.",
            "publisher_url": f"https://doi.org/{doi}",
        }

    if resp.status_code != 200:
        return {"error": f"Unpaywall API error: {resp.status_code}"}

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
    Check open access status for multiple DOIs.

    Parameters:
        dois: List of DOI strings (max 50 recommended per batch).

    Returns:
        List of dicts with doi, is_oa, pdf_url, and source for each.
    """
    results = []
    for doi in dois:
        doi = _clean_doi(doi)
        if not doi:
            results.append({"doi": doi, "error": "Invalid DOI"})
            continue

        try:
            result = get_paper_pdf(doi)
            results.append({
                "doi": doi,
                "is_oa": result.get("is_oa", False),
                "pdf_url": result.get("pdf_url"),
                "source": result.get("source", "none"),
                "message": result.get("message", ""),
            })
        except Exception as e:
            results.append({"doi": doi, "error": str(e)})

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
