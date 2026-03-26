"""
OpenAlex API client.

OpenAlex (https://openalex.org) is a free, open catalog of the global research system
with 250M+ works. No API key required. Polite pool (faster responses) available by
setting a mailto email in the OPENALEX_EMAIL environment variable.

Rate limits: Generous — 10 requests/second for polite pool, 1/sec without.
This is the highest-throughput academic API available.
"""

from typing import Any, Dict, List, Optional
import http_client
import cache

OPENALEX_BASE = "https://api.openalex.org"


def _params_with_email(params: Dict) -> Dict:
    """Add mailto parameter for polite pool if email is configured."""
    email = http_client.get_env("OPENALEX_EMAIL")
    if email:
        params["mailto"] = email
    return params


def search_works(
    query: str,
    num_results: int = 10,
    year: Optional[str] = None,
    open_access_only: bool = False,
    sort_by: str = "relevance_score",
) -> List[Dict[str, Any]]:
    """
    Search OpenAlex for works (papers, articles, preprints, etc.).

    Parameters:
        query: Search query.
        num_results: Number of results (max 200).
        year: Year filter (e.g., "2020", "2020-2025", ">2022").
        open_access_only: Only return open-access works.
        sort_by: Sort order — "relevance_score", "cited_by_count",
                 "publication_date".

    Returns:
        List of work dicts with title, authors, DOI, citations, etc.
    """
    url = f"{OPENALEX_BASE}/works"
    params = _params_with_email({
        "search": query,
        "per_page": min(num_results, 200),
        "sort": f"{sort_by}:desc" if sort_by == "relevance_score" else f"{sort_by}:desc",
    })

    filters = []
    if year:
        if "-" in year:
            start, end = year.split("-", 1)
            if start and end:
                filters.append(f"publication_year:{start}-{end}")
            elif start:
                filters.append(f"from_publication_date:{start}-01-01")
            elif end:
                filters.append(f"to_publication_date:{end}-12-31")
        elif year.startswith(">"):
            filters.append(f"from_publication_date:{year[1:]}-01-01")
        else:
            filters.append(f"publication_year:{year}")

    if open_access_only:
        filters.append("is_oa:true")

    if filters:
        params["filter"] = ",".join(filters)

    resp = http_client.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    return [_format_work(w) for w in data.get("results", [])]


def get_work(work_id: str) -> Dict[str, Any]:
    """
    Get details for a specific work by OpenAlex ID, DOI, PMID, or other identifier.

    Parameters:
        work_id: OpenAlex ID (e.g., "W2741809807"), DOI (e.g., "doi:10.1038/s41591-023-02437-x"),
                 or PMID (e.g., "pmid:37890456").

    Returns:
        Dict with full work details.
    """
    # Normalize DOI format
    if work_id.startswith("10."):
        work_id = f"doi:{work_id}"
    elif work_id.startswith("DOI:"):
        work_id = f"doi:{work_id[4:]}"

    url = f"{OPENALEX_BASE}/works/{work_id}"
    params = _params_with_email({})
    resp = http_client.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    work = _format_work(data)

    # Add referenced works
    refs = data.get("referenced_works", []) or []
    work["referenced_work_ids"] = refs[:30]

    # Add related works
    related = data.get("related_works", []) or []
    work["related_work_ids"] = related[:10]

    # Add concepts/topics
    concepts = data.get("concepts", []) or []
    work["concepts"] = [
        {"name": c.get("display_name", ""), "score": c.get("score", 0)}
        for c in concepts[:10]
    ]

    return work


def search_authors(
    query: str,
    num_results: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search for authors on OpenAlex.

    Parameters:
        query: Author name.
        num_results: Number of results.

    Returns:
        List of author dicts with name, affiliations, works count, citation count.
    """
    url = f"{OPENALEX_BASE}/authors"
    params = _params_with_email({
        "search": query,
        "per_page": min(num_results, 200),
    })
    resp = http_client.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    authors = []
    for a in data.get("results", []):
        last_institution = a.get("last_known_institutions", []) or a.get("last_known_institution")
        if isinstance(last_institution, list):
            affiliations = [inst.get("display_name", "") for inst in last_institution if inst]
        elif isinstance(last_institution, dict) and last_institution:
            affiliations = [last_institution.get("display_name", "")]
        else:
            affiliations = []

        authors.append({
            "openalex_id": a.get("id", ""),
            "name": a.get("display_name", ""),
            "affiliations": affiliations,
            "works_count": a.get("works_count", 0),
            "cited_by_count": a.get("cited_by_count", 0),
            "h_index": a.get("summary_stats", {}).get("h_index", 0),
            "orcid": (a.get("ids", {}) or {}).get("orcid", ""),
            "openalex_url": a.get("id", ""),
        })
    return authors


def get_author(author_id: str) -> Dict[str, Any]:
    """
    Get detailed author information from OpenAlex.

    Parameters:
        author_id: OpenAlex author ID (e.g., "A5023888391") or ORCID
                   (e.g., "orcid:0000-0002-1234-5678").

    Returns:
        Dict with author details.
    """
    if author_id.startswith("0000-"):
        author_id = f"orcid:{author_id}"

    url = f"{OPENALEX_BASE}/authors/{author_id}"
    params = _params_with_email({})
    resp = http_client.get(url, params=params)
    resp.raise_for_status()
    a = resp.json()

    last_institution = a.get("last_known_institutions", []) or a.get("last_known_institution")
    if isinstance(last_institution, list):
        affiliations = [inst.get("display_name", "") for inst in last_institution if inst]
    elif isinstance(last_institution, dict) and last_institution:
        affiliations = [last_institution.get("display_name", "")]
    else:
        affiliations = []

    return {
        "openalex_id": a.get("id", ""),
        "name": a.get("display_name", ""),
        "affiliations": affiliations,
        "works_count": a.get("works_count", 0),
        "cited_by_count": a.get("cited_by_count", 0),
        "h_index": a.get("summary_stats", {}).get("h_index", 0),
        "i10_index": a.get("summary_stats", {}).get("i10_index", 0),
        "2yr_mean_citedness": a.get("summary_stats", {}).get("2yr_mean_citedness", 0),
        "orcid": (a.get("ids", {}) or {}).get("orcid", ""),
        "topics": [
            t.get("display_name", "")
            for t in (a.get("topics", []) or [])[:10]
        ],
        "openalex_url": a.get("id", ""),
    }


def get_author_works(
    author_id: str,
    num_results: int = 20,
    sort_by: str = "publication_date",
) -> List[Dict[str, Any]]:
    """
    Get works by a specific author from OpenAlex.

    Parameters:
        author_id: OpenAlex author ID or ORCID.
        num_results: Number of works.
        sort_by: Sort order — "publication_date", "cited_by_count".

    Returns:
        List of work dicts.
    """
    if author_id.startswith("0000-"):
        author_id = f"orcid:{author_id}"
    # Extract the raw ID for filtering
    raw_id = author_id.split("/")[-1] if "/" in author_id else author_id

    url = f"{OPENALEX_BASE}/works"
    params = _params_with_email({
        "filter": f"author.id:{raw_id}",
        "per_page": min(num_results, 200),
        "sort": f"{sort_by}:desc" if sort_by == "relevance_score" else f"{sort_by}:desc",
    })
    resp = http_client.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    return [_format_work(w) for w in data.get("results", [])]


def get_institution(institution_id: str) -> Dict[str, Any]:
    """
    Get institution details from OpenAlex.

    Parameters:
        institution_id: OpenAlex institution ID or ROR ID.

    Returns:
        Dict with institution details.
    """
    url = f"{OPENALEX_BASE}/institutions/{institution_id}"
    params = _params_with_email({})
    resp = http_client.get(url, params=params)
    resp.raise_for_status()
    i = resp.json()

    return {
        "openalex_id": i.get("id", ""),
        "name": i.get("display_name", ""),
        "country": i.get("country_code", ""),
        "type": i.get("type", ""),
        "works_count": i.get("works_count", 0),
        "cited_by_count": i.get("cited_by_count", 0),
        "homepage": i.get("homepage_url", ""),
        "ror": (i.get("ids", {}) or {}).get("ror", ""),
    }


# --- Helper ---

def _format_work(item: Dict) -> Dict[str, Any]:
    """Format an OpenAlex work response into a clean dict."""
    authorships = item.get("authorships", []) or []
    authors = []
    for a in authorships[:15]:
        author_info = a.get("author", {}) or {}
        authors.append(author_info.get("display_name", ""))

    ids = item.get("ids", {}) or {}
    primary_location = item.get("primary_location", {}) or {}
    source = primary_location.get("source", {}) or {}
    oa = item.get("open_access", {}) or {}
    biblio = item.get("biblio", {}) or {}

    # Reconstruct abstract from inverted index (OpenAlex stores abstracts this way)
    abstract = ""
    aii = item.get("abstract_inverted_index", {}) or {}
    if aii:
        positions = {}
        for word, pos_list in aii.items():
            for pos in pos_list:
                positions[pos] = word
        if positions:
            abstract = " ".join(positions[i] for i in sorted(positions.keys()))

    return {
        "openalex_id": item.get("id", ""),
        "title": item.get("title", ""),
        "abstract": abstract,
        "authors": authors,
        "year": item.get("publication_year"),
        "publication_date": item.get("publication_date", ""),
        "venue": source.get("display_name", ""),
        "cited_by_count": item.get("cited_by_count", 0),
        "doi": (ids.get("doi", "") or "").replace("https://doi.org/", ""),
        "pmid": (ids.get("pmid", "") or "").replace("https://pubmed.ncbi.nlm.nih.gov/", ""),
        "type": item.get("type", ""),
        "is_open_access": oa.get("is_oa", False),
        "open_access_url": oa.get("oa_url", ""),
        "volume": biblio.get("volume", ""),
        "issue": biblio.get("issue", ""),
        "pages": f"{biblio.get('first_page', '')}-{biblio.get('last_page', '')}".strip("-"),
        "openalex_url": item.get("id", ""),
    }
