"""
PubMed/NCBI E-utilities client.

Supports full PubMed query syntax: MeSH terms, Boolean operators, field tags.
Uses ESearch + EFetch pipeline with WebEnv for pagination of large result sets.

Rate limits: 3 requests/sec without API key, 10/sec with NCBI_API_KEY.
"""

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import http_client
import cache

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EFETCH_BATCH_SIZE = 200


def _api_params() -> Dict[str, str]:
    """Base params including API key if available."""
    params = {"db": "pubmed"}
    api_key = http_client.get_env("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    return params


def _rate_delay() -> float:
    """Delay between requests based on whether API key is set."""
    return 0.1 if http_client.get_env("NCBI_API_KEY") else 0.34


def esearch(
    query: str, max_results: int = 100, use_history: bool = True
) -> Dict[str, Any]:
    """Search PubMed and return PMIDs. Supports full PubMed syntax."""
    params = _api_params()
    params.update(
        {
            "term": query,
            "retmax": min(max_results, 10000),
            "retmode": "json",
        }
    )
    if use_history:
        params["usehistory"] = "y"

    resp = http_client.get(f"{EUTILS_BASE}/esearch.fcgi", params=params)
    resp.raise_for_status()
    data = resp.json()
    result_data = data.get("esearchresult", {})

    output = {
        "pmids": result_data.get("idlist", []),
        "total_count": int(result_data.get("count", 0)),
        "query_translation": result_data.get("querytranslation", ""),
    }
    if use_history:
        output["webenv"] = result_data.get("webenv", "")
        output["query_key"] = result_data.get("querykey", "")
    return output


def efetch(
    pmids=None, webenv=None, query_key=None, retstart=0, retmax=200
) -> List[Dict[str, Any]]:
    """Fetch full article metadata from PubMed. Parses XML into standardized paper dicts."""
    params = _api_params()
    params["rettype"] = "xml"
    params["retmode"] = "xml"

    if pmids:
        params["id"] = ",".join(pmids[:retmax])
    elif webenv and query_key:
        params["WebEnv"] = webenv
        params["query_key"] = query_key
        params["retstart"] = retstart
        params["retmax"] = retmax
    else:
        return []

    resp = http_client.get(f"{EUTILS_BASE}/efetch.fcgi", params=params)
    resp.raise_for_status()
    return _parse_pubmed_xml(resp.content)


def _parse_pubmed_xml(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse PubMed XML into standardized paper dicts."""
    root = ET.fromstring(xml_bytes)
    papers = []
    for article_elem in root.findall(".//PubmedArticle"):
        paper = _parse_article(article_elem)
        if paper:
            papers.append(paper)
    return papers


def _parse_article(article_elem) -> Optional[Dict[str, Any]]:
    """Parse a single PubmedArticle XML element."""
    citation = article_elem.find("MedlineCitation")
    if citation is None:
        return None
    article = citation.find("Article")
    if article is None:
        return None

    # PMID
    pmid_elem = citation.find("PMID")
    pmid = pmid_elem.text if pmid_elem is not None else ""

    # Title
    title_elem = article.find("ArticleTitle")
    title = title_elem.text if title_elem is not None else ""

    # Abstract (handle structured abstracts with labels)
    abstract_parts = []
    abstract_elem = article.find("Abstract")
    if abstract_elem is not None:
        for text_elem in abstract_elem.findall("AbstractText"):
            label = text_elem.get("Label", "")
            text = text_elem.text or ""
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
    abstract = " ".join(abstract_parts)

    # Authors
    authors = []
    author_list = article.find("AuthorList")
    if author_list is not None:
        for author_elem in author_list.findall("Author"):
            last = author_elem.findtext("LastName", "")
            initials = author_elem.findtext("Initials", "")
            if last:
                authors.append(f"{last} {initials}".strip())

    # DOI — check ELocationID first, then ArticleIdList
    doi = ""
    for eloc in article.findall("ELocationID"):
        if eloc.get("EIdType") == "doi":
            doi = eloc.text or ""
            break
    if not doi:
        id_list = article_elem.find(".//ArticleIdList")
        if id_list is not None:
            for aid in id_list.findall("ArticleId"):
                if aid.get("IdType") == "doi":
                    doi = aid.text or ""
                    break

    # Year
    year = None
    journal_issue = article.find("Journal/JournalIssue")
    if journal_issue is not None:
        pub_date = journal_issue.find("PubDate")
        if pub_date is not None:
            year_elem = pub_date.find("Year")
            if year_elem is not None:
                try:
                    year = int(year_elem.text)
                except (ValueError, TypeError):
                    pass

    # Journal
    journal_elem = article.find("Journal/Title")
    journal = journal_elem.text if journal_elem is not None else ""

    # Volume, Issue, Pages
    volume = ""
    issue = ""
    if journal_issue is not None:
        vol_elem = journal_issue.find("Volume")
        volume = vol_elem.text if vol_elem is not None else ""
        iss_elem = journal_issue.find("Issue")
        issue = iss_elem.text if iss_elem is not None else ""
    pages_elem = article.find("Pagination/MedlinePgn")
    pages = pages_elem.text if pages_elem is not None else ""

    # MeSH headings
    mesh_headings = []
    mesh_list = citation.find("MeshHeadingList")
    if mesh_list is not None:
        for heading in mesh_list.findall("MeshHeading"):
            desc = heading.find("DescriptorName")
            if desc is not None and desc.text:
                mesh_headings.append(desc.text)

    # Publication types
    pub_types = []
    pub_type_list = article.find("PublicationTypeList")
    if pub_type_list is not None:
        for pt in pub_type_list.findall("PublicationType"):
            if pt.text:
                pub_types.append(pt.text)

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "doi": doi,
        "pmid": pmid,
        "abstract": abstract,
        "journal": journal,
        "volume": volume,
        "issue": issue,
        "pages": pages,
        "mesh_headings": mesh_headings,
        "publication_types": pub_types,
        "source": "pubmed",
    }


@cache.cached(category="search", ttl=cache.SEARCH_TTL)
def search_pubmed(query: str, max_results: int = 100) -> Dict[str, Any]:
    """Search PubMed and return full article metadata."""
    max_results = max(1, min(max_results, 10000))
    search_result = esearch(query, max_results=max_results, use_history=True)
    pmids = search_result["pmids"]

    if not pmids:
        return {
            "total_count": search_result["total_count"],
            "query_translation": search_result["query_translation"],
            "papers": [],
        }

    all_papers = []
    webenv = search_result.get("webenv", "")
    query_key = search_result.get("query_key", "")

    if webenv and query_key and len(pmids) > EFETCH_BATCH_SIZE:
        for start in range(0, len(pmids), EFETCH_BATCH_SIZE):
            batch = efetch(
                webenv=webenv,
                query_key=query_key,
                retstart=start,
                retmax=EFETCH_BATCH_SIZE,
            )
            all_papers.extend(batch)
            if start + EFETCH_BATCH_SIZE < len(pmids):
                time.sleep(_rate_delay())
    else:
        all_papers = efetch(pmids=pmids)

    return {
        "total_count": search_result["total_count"],
        "query_translation": search_result["query_translation"],
        "papers": all_papers,
    }
