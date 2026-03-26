"""
ORCID Public API client.

Uses the ORCID public API (https://pub.orcid.org/v3.0/) which requires no
authentication for read-only access to public profiles. Returns structured
data about researchers including employment history, publications, funding,
and education.
"""

from typing import Any, Dict, List, Optional
import http_client
import cache

ORCID_API_BASE = "https://pub.orcid.org/v3.0"
HEADERS = {"Accept": "application/json"}


def search_orcid(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search ORCID for researchers by name, affiliation, or keyword.

    Parameters:
        query (str): Search string (e.g., "Ali Soroush", "Mount Sinai gastroenterology")
        num_results (int): Maximum results to return.

    Returns:
        List of dicts with orcid_id, given_name, family_name, and affiliation.
    """
    url = f"{ORCID_API_BASE}/search/"
    params = {"q": query, "rows": num_results}
    resp = http_client.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("result", []):
        orcid_id = item.get("orcid-identifier", {}).get("path", "")
        # Fetch minimal profile for each result
        profile = _get_minimal_profile(orcid_id)
        results.append(profile)

    return results


def get_orcid_profile(orcid_id: str) -> Dict[str, Any]:
    """
    Get a full ORCID profile by ORCID iD.

    Parameters:
        orcid_id (str): The ORCID iD (e.g., "0000-0002-1234-5678")

    Returns:
        Dict with name, affiliation, employment history, education, keywords,
        external identifiers, and biography.
    """
    url = f"{ORCID_API_BASE}/{orcid_id}/person"
    resp = http_client.get(url, headers=HEADERS)
    resp.raise_for_status()
    person = resp.json()

    name_data = person.get("name", {}) or {}
    given = name_data.get("given-names", {})
    family = name_data.get("family-name", {})
    bio_data = person.get("biography", {}) or {}

    profile = {
        "orcid_id": orcid_id,
        "orcid_url": f"https://orcid.org/{orcid_id}",
        "given_name": given.get("value", "") if given else "",
        "family_name": family.get("value", "") if family else "",
        "biography": bio_data.get("content", "") if bio_data else "",
        "keywords": _extract_keywords(person),
        "external_ids": _extract_external_ids(person),
    }

    # Add employment
    profile["employments"] = get_orcid_employments(orcid_id)
    # Add education
    profile["education"] = get_orcid_education(orcid_id)

    return profile


def get_orcid_works(orcid_id: str, max_works: int = 20) -> List[Dict[str, Any]]:
    """
    Get publications from an ORCID profile.

    Parameters:
        orcid_id (str): The ORCID iD.
        max_works (int): Maximum number of works to return.

    Returns:
        List of dicts with title, journal, year, doi, type, and external_ids.
    """
    url = f"{ORCID_API_BASE}/{orcid_id}/works"
    resp = http_client.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    works = []
    for group in data.get("group", [])[:max_works]:
        summaries = group.get("work-summary", [])
        if not summaries:
            continue
        summary = summaries[0]  # Take the preferred/first summary

        title_data = summary.get("title", {}) or {}
        title_val = title_data.get("title", {}) or {}
        journal_data = summary.get("journal-title", {}) or {}
        pub_date = summary.get("publication-date", {}) or {}

        year = ""
        if pub_date and pub_date.get("year"):
            year = pub_date["year"].get("value", "")

        # Extract DOI and other identifiers
        ext_ids = summary.get("external-ids", {}) or {}
        doi = ""
        pmid = ""
        all_ids = {}
        for eid in ext_ids.get("external-id", []):
            id_type = eid.get("external-id-type", "")
            id_value = eid.get("external-id-value", "")
            all_ids[id_type] = id_value
            if id_type == "doi":
                doi = id_value
            elif id_type == "pmid":
                pmid = id_value

        works.append({
            "title": title_val.get("value", ""),
            "journal": journal_data.get("value", "") if journal_data else "",
            "year": year,
            "type": summary.get("type", ""),
            "doi": doi,
            "pmid": pmid,
            "external_ids": all_ids,
        })

    return works


def get_orcid_employments(orcid_id: str) -> List[Dict[str, Any]]:
    """
    Get employment history from an ORCID profile.

    Parameters:
        orcid_id (str): The ORCID iD.

    Returns:
        List of dicts with organization, department, role, start_date, end_date.
    """
    url = f"{ORCID_API_BASE}/{orcid_id}/employments"
    resp = http_client.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    employments = []
    for group in data.get("affiliation-group", []):
        for summary in group.get("summaries", []):
            emp = summary.get("employment-summary", {})
            org = emp.get("organization", {}) or {}
            start = emp.get("start-date", {}) or {}
            end = emp.get("end-date", {}) or {}

            employments.append({
                "organization": org.get("name", ""),
                "department": emp.get("department-name", ""),
                "role": emp.get("role-title", ""),
                "start_date": _format_date(start),
                "end_date": _format_date(end) if end else "present",
            })

    return employments


def get_orcid_education(orcid_id: str) -> List[Dict[str, Any]]:
    """
    Get education history from an ORCID profile.

    Parameters:
        orcid_id (str): The ORCID iD.

    Returns:
        List of dicts with organization, department, role, start_date, end_date.
    """
    url = f"{ORCID_API_BASE}/{orcid_id}/educations"
    resp = http_client.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    educations = []
    for group in data.get("affiliation-group", []):
        for summary in group.get("summaries", []):
            edu = summary.get("education-summary", {})
            org = edu.get("organization", {}) or {}
            start = edu.get("start-date", {}) or {}
            end = edu.get("end-date", {}) or {}

            educations.append({
                "organization": org.get("name", ""),
                "department": edu.get("department-name", ""),
                "degree": edu.get("role-title", ""),
                "start_date": _format_date(start),
                "end_date": _format_date(end) if end else "",
            })

    return educations


def get_orcid_funding(orcid_id: str) -> List[Dict[str, Any]]:
    """
    Get funding/grants from an ORCID profile.

    Parameters:
        orcid_id (str): The ORCID iD.

    Returns:
        List of dicts with title, funder, type, start_date, end_date, grant_number.
    """
    url = f"{ORCID_API_BASE}/{orcid_id}/fundings"
    resp = http_client.get(url, headers=HEADERS)
    resp.raise_for_status()
    data = resp.json()

    fundings = []
    for group in data.get("group", []):
        for summary in group.get("funding-summary", []):
            title_data = summary.get("title", {}) or {}
            title_val = title_data.get("title", {}) or {}
            org = summary.get("organization", {}) or {}
            start = summary.get("start-date", {}) or {}
            end = summary.get("end-date", {}) or {}

            # Extract grant number from external IDs
            ext_ids = summary.get("external-ids", {}) or {}
            grant_number = ""
            for eid in ext_ids.get("external-id", []):
                if eid.get("external-id-type") == "grant_number":
                    grant_number = eid.get("external-id-value", "")

            fundings.append({
                "title": title_val.get("value", ""),
                "funder": org.get("name", ""),
                "type": summary.get("type", ""),
                "start_date": _format_date(start),
                "end_date": _format_date(end) if end else "",
                "grant_number": grant_number,
            })

    return fundings


# --- Helper functions ---

def _get_minimal_profile(orcid_id: str) -> Dict[str, Any]:
    """Fetch just name and current affiliation for search results."""
    url = f"{ORCID_API_BASE}/{orcid_id}/person"
    try:
        resp = http_client.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        person = resp.json()

        name_data = person.get("name", {}) or {}
        given = name_data.get("given-names", {})
        family = name_data.get("family-name", {})

        return {
            "orcid_id": orcid_id,
            "orcid_url": f"https://orcid.org/{orcid_id}",
            "given_name": given.get("value", "") if given else "",
            "family_name": family.get("value", "") if family else "",
        }
    except Exception:
        return {"orcid_id": orcid_id, "orcid_url": f"https://orcid.org/{orcid_id}"}


def _extract_keywords(person: dict) -> List[str]:
    """Extract keywords from ORCID person data."""
    kw_data = person.get("keywords", {}) or {}
    keywords = []
    for kw in kw_data.get("keyword", []):
        content = kw.get("content", "")
        if content:
            keywords.append(content)
    return keywords


def _extract_external_ids(person: dict) -> Dict[str, str]:
    """Extract external identifiers (Scopus, ResearcherID, etc.)."""
    ids_data = person.get("external-identifiers", {}) or {}
    ids = {}
    for eid in ids_data.get("external-identifier", []):
        id_type = eid.get("external-id-type", "")
        id_value = eid.get("external-id-value", "")
        if id_type and id_value:
            ids[id_type] = id_value
    return ids


def _format_date(date_dict: Optional[Dict]) -> str:
    """Format an ORCID date dict into YYYY-MM string."""
    if not date_dict:
        return ""
    year = date_dict.get("year", {})
    month = date_dict.get("month", {})
    y = year.get("value", "") if year else ""
    m = month.get("value", "") if month else ""
    if y and m:
        return f"{y}-{m}"
    return y or ""
