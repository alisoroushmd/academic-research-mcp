# Systematic Review Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the academic-research MCP server with PubMed E-utilities, a stateful review library, snowball search, Zotero export, auto-logged search strategies, and PRISMA flow counts.

**Architecture:** Review-centric design — a persistent SQLite review library is the central state model. Searches auto-log and auto-deduplicate when a review is active. New `db.py` module extracted from `cache.py` provides shared DB access. New `pubmed_client.py` follows existing client patterns (synchronous functions, `http_client` for requests, `cache.cached` decorator). New `review_manager.py` manages all review state. Tools added to `server.py` follow existing patterns (`asyncio.to_thread` wrappers, `_error_dict`/`_error_list` helpers).

**Tech Stack:** Python 3.13, FastMCP, SQLite (WAL mode), NCBI E-utilities (XML via stdlib `xml.etree.ElementTree`), existing `http_client` module for HTTP, existing `cache` module for caching.

**Spec:** `docs/superpowers/specs/2026-04-10-systematic-review-features-design.md`

**Project root:** `/Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `db.py` | Create | Shared SQLite connection, `_get_db()`, `_get_db_path()`, WAL mode init |
| `cache.py` | Modify | Replace internal DB management with `import db` |
| `pubmed_client.py` | Create | NCBI E-utilities: esearch, efetch, search_pubmed |
| `review_manager.py` | Create | Review CRUD, paper dedup, search logging, PRISMA counts, active review state |
| `orchestrator.py` | Modify | Add pubmed to `_query_source` and `smart_search`, add `snowball_search` |
| `server.py` | Modify | Add 10 new tools, add auto-logging hooks to existing search tools |
| `tests/test_db.py` | Create | Tests for shared DB module |
| `tests/test_pubmed_client.py` | Create | Tests for PubMed client (mocked HTTP) |
| `tests/test_review_manager.py` | Create | Tests for review library state management |
| `tests/test_snowball.py` | Create | Tests for snowball search logic |
| `tests/test_prisma_counts.py` | Create | Tests for PRISMA flow count computation |
| `tests/conftest.py` | Create | Shared fixtures (temp DB, sample paper dicts) |

---

## Task 1: Extract shared DB module from cache.py

**Files:**
- Create: `db.py`
- Modify: `cache.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Create `tests/` directory and `conftest.py`**

```bash
mkdir -p tests
```

```python
# tests/conftest.py
import os
import tempfile
import pytest

@pytest.fixture
def tmp_db_dir(tmp_path, monkeypatch):
    """Point the DB to a temp directory for isolated tests."""
    monkeypatch.setenv("ACADEMIC_CACHE_DIR", str(tmp_path))
    # Reset the singleton so it picks up the new path
    import db
    db._conn = None
    yield tmp_path
    # Cleanup singleton
    if db._conn is not None:
        db._conn.close()
        db._conn = None


SAMPLE_PAPER = {
    "title": "Deep learning for gastric intestinal metaplasia detection",
    "authors": ["Soroush A", "Patel B"],
    "year": 2024,
    "doi": "10.1234/test.2024.001",
    "pmid": "39876543",
    "abstract": "We developed a deep learning model...",
    "source": "openalex",
    "citation_count": 12,
}

SAMPLE_PAPER_NO_DOI = {
    "title": "Conference abstract on gastric cancer screening",
    "authors": ["Smith J"],
    "year": 2023,
    "doi": None,
    "pmid": None,
    "abstract": "This is a conference abstract...",
    "source": "s2",
    "citation_count": 0,
}

SAMPLE_PAPER_DUPLICATE = {
    "title": "Deep learning for gastric intestinal metaplasia detection",
    "authors": ["Soroush A", "Patel B", "Chen C"],
    "year": 2024,
    "doi": "10.1234/TEST.2024.001",  # same DOI, different case
    "pmid": None,
    "abstract": "A different abstract text...",
    "source": "s2",
    "citation_count": 15,
}
```

- [ ] **Step 2: Write failing test for db module**

```python
# tests/test_db.py
import sqlite3
import os
from tests.conftest import *


def test_get_db_returns_connection(tmp_db_dir):
    import db
    conn = db.get_db()
    assert isinstance(conn, sqlite3.Connection)


def test_get_db_creates_file(tmp_db_dir):
    import db
    db.get_db()
    db_path = db.get_db_path()
    assert os.path.exists(db_path)


def test_get_db_singleton(tmp_db_dir):
    import db
    conn1 = db.get_db()
    conn2 = db.get_db()
    assert conn1 is conn2


def test_get_db_wal_mode(tmp_db_dir):
    import db
    conn = db.get_db()
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 4: Create `db.py`**

```python
# db.py
"""
Shared SQLite database connection for academic-research MCP.

Provides a singleton WAL-mode SQLite connection used by both cache.py
and review_manager.py. The DB file lives at
~/.cache/academic-research-mcp/cache.db by default (override with
ACADEMIC_CACHE_DIR env var).
"""

import os
import sqlite3
import threading
from typing import Optional

_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def get_db_path() -> str:
    """Get the database file path (resolved at call time, not import time)."""
    cache_dir = os.environ.get(
        "ACADEMIC_CACHE_DIR",
        os.path.expanduser("~/.cache/academic-research-mcp"),
    )
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "cache.db")


def get_db() -> sqlite3.Connection:
    """Get or create the singleton database connection with WAL mode."""
    global _conn
    if _conn is not None:
        return _conn

    with _lock:
        if _conn is not None:
            return _conn

        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        _conn = conn

    return _conn
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -m pytest tests/test_db.py -v`
Expected: 4 passed

- [ ] **Step 6: Refactor `cache.py` to use `db.py`**

In `cache.py`, replace the internal `_conn`, `_lock`, `_get_cache_path`, and `_get_db` with imports from `db`:

Remove these lines (approx lines 17-73 of current cache.py):
```python
# DELETE: _conn, _lock, _get_cache_path(), _get_db() — all replaced by db module
```

Replace with:
```python
import db as _db

_lock = _db._lock  # reuse the same threading lock
```

Then replace every `_get_db()` call with `_db.get_db()` and every `_get_cache_path()` call with `_db.get_db_path()`.

Move the cache table creation into a `_ensure_tables()` function called on first use:

```python
_tables_created = False

def _ensure_cache_table():
    global _tables_created
    if _tables_created:
        return
    conn = _db.get_db()
    with _lock:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at REAL NOT NULL,
                ttl REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cache_category
            ON cache(category)
        """)
        conn.commit()
    _tables_created = True
```

Add `_ensure_cache_table()` as the first line in `get()`, `put()`, `clear()`, `stats()`, and `cleanup()`.

- [ ] **Step 7: Verify existing cache tests pass (manual smoke test)**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -c "import cache; print(cache.stats())"`
Expected: Returns stats dict without error

- [ ] **Step 8: Commit**

```bash
git add db.py cache.py tests/conftest.py tests/test_db.py
git commit -m "refactor: extract shared db module from cache.py

Shared SQLite connection now lives in db.py, used by both cache.py
and the upcoming review_manager.py."
```

---

## Task 2: PubMed E-utilities client

**Files:**
- Create: `pubmed_client.py`
- Create: `tests/test_pubmed_client.py`

- [ ] **Step 1: Write failing tests for PubMed client**

```python
# tests/test_pubmed_client.py
"""Tests for PubMed E-utilities client using mocked HTTP responses."""
import json
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock
import pytest


# --- Sample E-utilities responses ---

ESEARCH_RESPONSE = {
    "esearchresult": {
        "count": "2847",
        "retmax": "3",
        "idlist": ["39876543", "39654321", "39123456"],
        "webenv": "MCID_abc123",
        "querykey": "1",
        "querytranslation": '"intestinal metaplasia"[MeSH Terms] AND "deep learning"[Title]',
    }
}

EFETCH_XML = """<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation Status="MEDLINE">
      <PMID Version="1">39876543</PMID>
      <Article>
        <Journal>
          <JournalIssue>
            <Volume>168</Volume>
            <Issue>3</Issue>
            <PubDate><Year>2024</Year><Month>Mar</Month></PubDate>
          </JournalIssue>
          <Title>Gastrointestinal Endoscopy</Title>
          <ISOAbbreviation>Gastrointest Endosc</ISOAbbreviation>
        </Journal>
        <ArticleTitle>Deep learning for gastric intestinal metaplasia detection.</ArticleTitle>
        <Abstract>
          <AbstractText>We developed a deep learning model for real-time detection.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author>
            <LastName>Soroush</LastName>
            <ForeName>Ali</ForeName>
            <Initials>A</Initials>
          </Author>
          <Author>
            <LastName>Patel</LastName>
            <ForeName>Bhavik</ForeName>
            <Initials>B</Initials>
          </Author>
        </AuthorList>
        <ELocationID EIdType="doi">10.1016/j.gie.2024.001</ELocationID>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName>Intestinal Metaplasia</DescriptorName>
        </MeshHeading>
        <MeshHeading>
          <DescriptorName>Deep Learning</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""


def _mock_esearch_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = ESEARCH_RESPONSE
    return resp


def _mock_efetch_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.text = EFETCH_XML
    resp.content = EFETCH_XML.encode("utf-8")
    return resp


@patch("http_client.get")
def test_esearch_returns_pmids(mock_get):
    mock_get.return_value = _mock_esearch_response()
    import pubmed_client
    result = pubmed_client.esearch("intestinal metaplasia[MeSH] AND deep learning[ti]", max_results=3)
    assert result["pmids"] == ["39876543", "39654321", "39123456"]
    assert result["total_count"] == 2847
    assert result["query_translation"] is not None


@patch("http_client.get")
def test_efetch_parses_xml(mock_get):
    mock_get.return_value = _mock_efetch_response()
    import pubmed_client
    papers = pubmed_client.efetch(["39876543"])
    assert len(papers) == 1
    paper = papers[0]
    assert paper["title"] == "Deep learning for gastric intestinal metaplasia detection."
    assert paper["pmid"] == "39876543"
    assert paper["doi"] == "10.1016/j.gie.2024.001"
    assert paper["year"] == 2024
    assert len(paper["authors"]) == 2
    assert "Soroush A" in paper["authors"]
    assert "Intestinal Metaplasia" in paper["mesh_headings"]


@patch("http_client.get")
def test_search_pubmed_end_to_end(mock_get):
    mock_get.side_effect = [_mock_esearch_response(), _mock_efetch_response()]
    import pubmed_client
    result = pubmed_client.search_pubmed("intestinal metaplasia", max_results=3)
    assert result["total_count"] == 2847
    assert len(result["papers"]) == 1  # only 1 in our mock XML
    assert result["papers"][0]["pmid"] == "39876543"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -m pytest tests/test_pubmed_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pubmed_client'`

- [ ] **Step 3: Implement `pubmed_client.py`**

```python
# pubmed_client.py
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
EFETCH_BATCH_SIZE = 200  # max PMIDs per efetch request


def _api_params() -> Dict[str, str]:
    """Base params including API key if available."""
    params = {"db": "pubmed"}
    api_key = http_client.get_env("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    return params


def _rate_delay() -> float:
    """Delay between requests based on whether API key is set."""
    return 0.1 if http_client.get_env("NCBI_API_KEY") else 0.34  # 10/sec vs 3/sec


def esearch(
    query: str,
    max_results: int = 100,
    use_history: bool = True,
) -> Dict[str, Any]:
    """
    Search PubMed and return PMIDs.

    Supports full PubMed syntax:
      - MeSH terms: "intestinal metaplasia"[MeSH]
      - Boolean: term1 AND term2 OR term3
      - Field tags: [ti], [au], [mh], [pt], [dp]

    Parameters:
        query: PubMed query string.
        max_results: Maximum PMIDs to return.
        use_history: Use WebEnv/QueryKey for large result sets.

    Returns:
        Dict with pmids, total_count, query_translation, and optionally
        webenv/query_key for pagination.
    """
    params = _api_params()
    params.update({
        "term": query,
        "retmax": min(max_results, 10000),
        "retmode": "json",
    })
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
    pmids: Optional[List[str]] = None,
    webenv: Optional[str] = None,
    query_key: Optional[str] = None,
    retstart: int = 0,
    retmax: int = 200,
) -> List[Dict[str, Any]]:
    """
    Fetch full article metadata from PubMed.

    Can fetch by PMID list or by WebEnv/QueryKey from a prior esearch.

    Parameters:
        pmids: List of PubMed IDs (mutually exclusive with webenv).
        webenv: WebEnv string from esearch history.
        query_key: QueryKey from esearch history.
        retstart: Start index for WebEnv pagination.
        retmax: Batch size (max 200 per NCBI guidelines).

    Returns:
        List of paper dicts with standardized fields.
    """
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


def _parse_article(article_elem: ET.Element) -> Optional[Dict[str, Any]]:
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

    # Abstract
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

    # DOI
    doi = ""
    for eloc in article.findall("ELocationID"):
        if eloc.get("EIdType") == "doi":
            doi = eloc.text or ""
            break
    # Also check ArticleIdList
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
def search_pubmed(
    query: str,
    max_results: int = 100,
) -> Dict[str, Any]:
    """
    Search PubMed and return full article metadata.

    Convenience wrapper: esearch -> efetch with automatic batching
    for large result sets.

    Parameters:
        query: PubMed query string (full E-utilities syntax supported).
        max_results: Maximum results to return (default: 100, max: 10000).

    Returns:
        Dict with total_count, query_translation, and papers list.
    """
    max_results = max(1, min(max_results, 10000))

    # Step 1: Search for PMIDs
    search_result = esearch(query, max_results=max_results, use_history=True)
    pmids = search_result["pmids"]

    if not pmids:
        return {
            "total_count": search_result["total_count"],
            "query_translation": search_result["query_translation"],
            "papers": [],
        }

    # Step 2: Fetch metadata in batches
    all_papers = []
    webenv = search_result.get("webenv", "")
    query_key = search_result.get("query_key", "")

    if webenv and query_key and len(pmids) > EFETCH_BATCH_SIZE:
        # Use WebEnv for large sets
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
        # Direct PMID fetch for small sets
        all_papers = efetch(pmids=pmids)

    return {
        "total_count": search_result["total_count"],
        "query_translation": search_result["query_translation"],
        "papers": all_papers,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -m pytest tests/test_pubmed_client.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add pubmed_client.py tests/test_pubmed_client.py
git commit -m "feat: add PubMed E-utilities client

Supports full PubMed query syntax (MeSH, Boolean, field tags),
esearch + efetch pipeline with WebEnv pagination for large result sets."
```

---

## Task 3: Review Manager — core state management

**Files:**
- Create: `review_manager.py`
- Create: `tests/test_review_manager.py`

- [ ] **Step 1: Write failing tests for review CRUD**

```python
# tests/test_review_manager.py
"""Tests for review library state management."""
import json
import pytest
from tests.conftest import SAMPLE_PAPER, SAMPLE_PAPER_NO_DOI, SAMPLE_PAPER_DUPLICATE


def test_create_review(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    review = rm.create_review("GIM SR", "Risk stratification of gastric intestinal metaplasia")
    assert review["name"] == "GIM SR"
    assert review["status"] == "active"
    assert "id" in review


def test_list_reviews_empty(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    reviews = rm.list_reviews()
    assert reviews == []


def test_list_reviews_with_data(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    rm.create_review("Review 1", "Description 1")
    rm.create_review("Review 2", "Description 2")
    reviews = rm.list_reviews()
    assert len(reviews) == 2


def test_get_review(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    created = rm.create_review("Test Review", "Test description")
    review = rm.get_review(created["id"])
    assert review["name"] == "Test Review"
    assert review["paper_counts"]["total"] == 0
    assert "searches" in review


def test_get_review_not_found(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    result = rm.get_review("nonexistent-id")
    assert "error" in result


def test_add_papers_dedup_by_doi(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    review = rm.create_review("Test", "Test")
    rid = review["id"]

    # Add first paper
    count1 = rm.add_papers(rid, "search-1", [SAMPLE_PAPER], "openalex")
    assert count1 == 1

    # Add duplicate (same DOI, different case)
    count2 = rm.add_papers(rid, "search-2", [SAMPLE_PAPER_DUPLICATE], "s2")
    assert count2 == 0  # deduped


def test_add_papers_dedup_by_pmid(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    review = rm.create_review("Test", "Test")
    rid = review["id"]

    rm.add_papers(rid, "search-1", [SAMPLE_PAPER], "openalex")

    # Same PMID, no DOI
    paper_same_pmid = {
        "title": "Different title entirely",
        "authors": ["Other A"],
        "year": 2024,
        "doi": None,
        "pmid": "39876543",  # same PMID as SAMPLE_PAPER
        "source": "pubmed",
    }
    count = rm.add_papers(rid, "search-2", [paper_same_pmid], "pubmed")
    assert count == 0


def test_add_papers_no_doi_no_pmid(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    review = rm.create_review("Test", "Test")
    rid = review["id"]

    count = rm.add_papers(rid, "search-1", [SAMPLE_PAPER_NO_DOI], "s2")
    assert count == 1


def test_update_paper_status(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    review = rm.create_review("Test", "Test")
    rid = review["id"]
    rm.add_papers(rid, "search-1", [SAMPLE_PAPER], "openalex")

    papers = rm.get_review_papers(rid)
    paper_id = papers[0]["id"]
    updated = rm.update_paper_status(rid, [paper_id], "screened_in")
    assert updated == 1

    papers = rm.get_review_papers(rid, status_filter="screened_in")
    assert len(papers) == 1


def test_log_search(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    review = rm.create_review("Test", "Test")
    rid = review["id"]

    search_id = rm.log_search(
        rid, "pubmed", "intestinal metaplasia[MeSH]",
        {"max_results": 100}, raw_count=842, new_count=615
    )
    assert search_id is not None

    review_detail = rm.get_review(rid)
    assert len(review_detail["searches"]) == 1
    assert review_detail["searches"][0]["source"] == "pubmed"


def test_set_active_review(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    review = rm.create_review("Test", "Test")
    rid = review["id"]

    result = rm.set_active_review(rid)
    assert result["active_review_id"] == rid
    assert rm.get_active_review() == rid

    # Deactivate
    result = rm.set_active_review(None)
    assert rm.get_active_review() is None


def test_set_active_review_invalid_id(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    result = rm.set_active_review("nonexistent-id")
    assert "error" in result


def test_get_review_papers_pagination(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    review = rm.create_review("Test", "Test")
    rid = review["id"]

    papers = [
        {"title": f"Paper {i}", "authors": [f"Author {i}"], "year": 2024,
         "doi": f"10.1234/test.{i}", "pmid": None, "source": "openalex"}
        for i in range(10)
    ]
    rm.add_papers(rid, "search-1", papers, "openalex")

    page1 = rm.get_review_papers(rid, offset=0, limit=5)
    assert len(page1) == 5
    page2 = rm.get_review_papers(rid, offset=5, limit=5)
    assert len(page2) == 5
    assert page1[0]["id"] != page2[0]["id"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -m pytest tests/test_review_manager.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'review_manager'`

- [ ] **Step 3: Implement `review_manager.py`**

```python
# review_manager.py
"""
Systematic review library state manager.

Manages reviews, paper deduplication, search logging, and PRISMA counts
in the shared SQLite database. The active review (in-memory state) enables
auto-logging from search tools.
"""

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import db as _db

logger = logging.getLogger(__name__)

_active_review_id: Optional[str] = None
_tables_initialized = False
_lock = _db._lock


def _ensure_tables():
    """Create review tables if they don't exist."""
    global _tables_initialized
    if _tables_initialized:
        return
    conn = _db.get_db()
    with _lock:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                query_description TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_searches (
                id TEXT PRIMARY KEY,
                review_id TEXT NOT NULL REFERENCES reviews(id),
                source TEXT NOT NULL,
                query TEXT NOT NULL,
                filters TEXT,
                executed_at REAL NOT NULL,
                result_count_raw INTEGER NOT NULL,
                result_count_new INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_review_searches_review
            ON review_searches(review_id)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_papers (
                id TEXT PRIMARY KEY,
                review_id TEXT NOT NULL REFERENCES reviews(id),
                doi TEXT,
                pmid TEXT,
                title TEXT NOT NULL,
                authors TEXT,
                year INTEGER,
                source TEXT NOT NULL,
                search_id TEXT REFERENCES review_searches(id),
                added_at REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                metadata TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rp_review ON review_papers(review_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rp_doi ON review_papers(doi)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rp_pmid ON review_papers(pmid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rp_status ON review_papers(review_id, status)")
        conn.commit()
    _tables_initialized = True


def create_review(name: str, query_description: str = "") -> Dict[str, Any]:
    """Create a new systematic review."""
    _ensure_tables()
    review_id = str(uuid.uuid4())
    now = time.time()
    conn = _db.get_db()
    with _lock:
        conn.execute(
            "INSERT INTO reviews (id, name, query_description, created_at, updated_at, status) VALUES (?, ?, ?, ?, ?, ?)",
            (review_id, name, query_description, now, now, "active"),
        )
        conn.commit()
    return {"id": review_id, "name": name, "query_description": query_description, "status": "active", "created_at": now}


def list_reviews() -> List[Dict[str, Any]]:
    """List all reviews with paper counts."""
    _ensure_tables()
    conn = _db.get_db()
    with _lock:
        rows = conn.execute(
            """SELECT r.id, r.name, r.query_description, r.status, r.created_at, r.updated_at,
                      (SELECT COUNT(*) FROM review_papers WHERE review_id = r.id) as paper_count
               FROM reviews r ORDER BY r.updated_at DESC"""
        ).fetchall()
    return [
        {"id": r[0], "name": r[1], "query_description": r[2], "status": r[3],
         "created_at": r[4], "updated_at": r[5], "paper_count": r[6]}
        for r in rows
    ]


def get_review(review_id: str) -> Dict[str, Any]:
    """Get full review details including search log and paper counts by status."""
    _ensure_tables()
    conn = _db.get_db()
    with _lock:
        row = conn.execute(
            "SELECT id, name, query_description, status, created_at, updated_at FROM reviews WHERE id = ?",
            (review_id,),
        ).fetchone()
    if row is None:
        return {"error": f"Review not found: {review_id}"}

    with _lock:
        # Paper counts by status
        status_rows = conn.execute(
            "SELECT status, COUNT(*) FROM review_papers WHERE review_id = ? GROUP BY status",
            (review_id,),
        ).fetchall()
        total_papers = conn.execute(
            "SELECT COUNT(*) FROM review_papers WHERE review_id = ?", (review_id,),
        ).fetchone()[0]

        # Search log
        search_rows = conn.execute(
            """SELECT id, source, query, filters, executed_at, result_count_raw, result_count_new
               FROM review_searches WHERE review_id = ? ORDER BY executed_at""",
            (review_id,),
        ).fetchall()

    paper_counts = {"total": total_papers}
    for s, c in status_rows:
        paper_counts[s] = c

    searches = [
        {"id": s[0], "source": s[1], "query": s[2], "filters": json.loads(s[3]) if s[3] else {},
         "executed_at": s[4], "result_count_raw": s[5], "result_count_new": s[6]}
        for s in search_rows
    ]

    return {
        "id": row[0], "name": row[1], "query_description": row[2], "status": row[3],
        "created_at": row[4], "updated_at": row[5],
        "paper_counts": paper_counts, "searches": searches,
    }


def add_papers(
    review_id: str,
    search_id: str,
    papers: List[Dict[str, Any]],
    source: str,
) -> int:
    """
    Add papers to a review, deduplicating against existing papers.
    Returns the count of new (non-duplicate) papers added.
    """
    _ensure_tables()
    new_count = 0
    conn = _db.get_db()
    now = time.time()

    for paper in papers:
        if is_duplicate(review_id, paper):
            continue

        paper_id = str(uuid.uuid4())
        doi = _extract_doi(paper)
        pmid = paper.get("pmid") or ""
        title = paper.get("title", "") or ""
        authors = json.dumps(paper.get("authors", []))
        year = paper.get("year")
        metadata = json.dumps(paper)

        with _lock:
            conn.execute(
                """INSERT INTO review_papers
                   (id, review_id, doi, pmid, title, authors, year, source, search_id, added_at, status, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)""",
                (paper_id, review_id, doi, pmid, title, authors, year, source, search_id, now, metadata),
            )
        new_count += 1

    with _lock:
        conn.commit()
        conn.execute("UPDATE reviews SET updated_at = ? WHERE id = ?", (now, review_id))
        conn.commit()

    return new_count


def is_duplicate(review_id: str, paper: Dict[str, Any]) -> bool:
    """Check if a paper already exists in the review."""
    conn = _db.get_db()

    # 1. DOI match
    doi = _extract_doi(paper)
    if doi:
        with _lock:
            row = conn.execute(
                "SELECT 1 FROM review_papers WHERE review_id = ? AND LOWER(doi) = ?",
                (review_id, doi.lower()),
            ).fetchone()
        if row:
            return True

    # 2. PMID match
    pmid = paper.get("pmid") or ""
    if pmid:
        with _lock:
            row = conn.execute(
                "SELECT 1 FROM review_papers WHERE review_id = ? AND pmid = ?",
                (review_id, pmid),
            ).fetchone()
        if row:
            return True

    # 3. Fuzzy title match
    title = paper.get("title", "") or ""
    if title:
        with _lock:
            existing_titles = conn.execute(
                "SELECT title FROM review_papers WHERE review_id = ?",
                (review_id,),
            ).fetchall()
        from orchestrator import _title_similarity
        for (existing_title,) in existing_titles:
            if _title_similarity(title, existing_title) >= 0.85:
                return True

    return False


def log_search(
    review_id: str,
    source: str,
    query: str,
    filters: Dict[str, Any],
    raw_count: int,
    new_count: int,
) -> str:
    """Log a search execution to the review."""
    _ensure_tables()
    search_id = str(uuid.uuid4())
    conn = _db.get_db()
    with _lock:
        conn.execute(
            """INSERT INTO review_searches
               (id, review_id, source, query, filters, executed_at, result_count_raw, result_count_new)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (search_id, review_id, source, query, json.dumps(filters), time.time(), raw_count, new_count),
        )
        conn.commit()
    return search_id


def update_paper_status(review_id: str, paper_ids: List[str], status: str) -> int:
    """Batch update screening status for papers in a review."""
    _ensure_tables()
    valid_statuses = {"new", "screened_in", "screened_out", "included"}
    if status not in valid_statuses:
        return 0

    conn = _db.get_db()
    placeholders = ",".join("?" * len(paper_ids))
    with _lock:
        cursor = conn.execute(
            f"UPDATE review_papers SET status = ? WHERE review_id = ? AND id IN ({placeholders})",
            [status, review_id] + paper_ids,
        )
        conn.commit()
    return cursor.rowcount


def get_review_papers(
    review_id: str,
    status_filter: Optional[str] = None,
    search_id: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get paginated papers from a review, optionally filtered."""
    _ensure_tables()
    conn = _db.get_db()
    query = "SELECT id, doi, pmid, title, authors, year, source, search_id, added_at, status FROM review_papers WHERE review_id = ?"
    params: list = [review_id]

    if status_filter:
        query += " AND status = ?"
        params.append(status_filter)
    if search_id:
        query += " AND search_id = ?"
        params.append(search_id)

    query += " ORDER BY added_at LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with _lock:
        rows = conn.execute(query, params).fetchall()

    return [
        {"id": r[0], "doi": r[1], "pmid": r[2], "title": r[3],
         "authors": json.loads(r[4]) if r[4] else [], "year": r[5],
         "source": r[6], "search_id": r[7], "added_at": r[8], "status": r[9]}
        for r in rows
    ]


def set_active_review(review_id: Optional[str]) -> Dict[str, Any]:
    """Set or clear the active review for auto-logging."""
    global _active_review_id

    if review_id is None:
        _active_review_id = None
        return {"active_review_id": None, "message": "Auto-logging deactivated"}

    _ensure_tables()
    conn = _db.get_db()
    with _lock:
        row = conn.execute("SELECT id FROM reviews WHERE id = ?", (review_id,)).fetchone()
    if row is None:
        return {"error": f"Review not found: {review_id}"}

    _active_review_id = review_id
    return {"active_review_id": review_id, "message": f"Auto-logging activated for review {review_id}"}


def get_active_review() -> Optional[str]:
    """Get the currently active review ID, or None."""
    return _active_review_id


def prisma_counts(review_id: str) -> Dict[str, Any]:
    """Compute PRISMA 2020 flow diagram counts for a review."""
    _ensure_tables()
    conn = _db.get_db()

    with _lock:
        # Check review exists
        row = conn.execute("SELECT id FROM reviews WHERE id = ?", (review_id,)).fetchone()
        if row is None:
            return {"error": f"Review not found: {review_id}"}

        # Search counts by source
        search_rows = conn.execute(
            "SELECT source, COUNT(*), SUM(result_count_raw) FROM review_searches WHERE review_id = ? GROUP BY source",
            (review_id,),
        ).fetchall()

        # Total raw records
        total_raw = conn.execute(
            "SELECT COALESCE(SUM(result_count_raw), 0) FROM review_searches WHERE review_id = ?",
            (review_id,),
        ).fetchone()[0]

        # Total unique papers
        total_unique = conn.execute(
            "SELECT COUNT(*) FROM review_papers WHERE review_id = ?",
            (review_id,),
        ).fetchone()[0]

        # Paper counts by status
        status_rows = conn.execute(
            "SELECT status, COUNT(*) FROM review_papers WHERE review_id = ? GROUP BY status",
            (review_id,),
        ).fetchall()

    # Build databases dict
    databases = {}
    other_methods = {}
    for source, search_count, record_sum in search_rows:
        entry = {"searches": search_count, "records": int(record_sum or 0)}
        if source == "snowball":
            other_methods["snowball"] = entry
        elif source == "smart_search":
            # smart_search aggregates multiple sources; report as-is
            databases["smart_search"] = entry
        else:
            databases[source] = entry

    status_counts = dict(status_rows)

    return {
        "identification": {
            "databases": databases,
            "other_methods": other_methods,
            "total_records": int(total_raw),
        },
        "duplicates_removed": int(total_raw) - total_unique,
        "unique_records": total_unique,
        "screening": {
            "screened": total_unique,
            "screened_out": status_counts.get("screened_out", 0),
            "sought_for_retrieval": status_counts.get("screened_in", 0),
        },
        "included": status_counts.get("included", 0),
    }


def update_search_new_count(search_id: str, new_count: int) -> None:
    """Update the result_count_new for a search after dedup is computed."""
    conn = _db.get_db()
    with _lock:
        conn.execute(
            "UPDATE review_searches SET result_count_new = ? WHERE id = ?",
            (new_count, search_id),
        )
        conn.commit()


def _extract_doi(paper: Dict) -> str:
    """Extract and clean DOI from a paper dict."""
    doi = paper.get("doi", "") or ""
    if doi:
        doi = doi.replace("https://doi.org/", "").strip()
    return doi
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -m pytest tests/test_review_manager.py -v`
Expected: All 13 tests pass

- [ ] **Step 5: Commit**

```bash
git add review_manager.py tests/test_review_manager.py
git commit -m "feat: add review manager with state, dedup, logging, PRISMA counts

Persistent review library in SQLite — supports paper dedup by DOI/PMID/title,
search logging, batch status updates, and PRISMA 2020 flow counts."
```

---

## Task 4: PRISMA counts tests

**Files:**
- Create: `tests/test_prisma_counts.py`

- [ ] **Step 1: Write PRISMA counts tests**

```python
# tests/test_prisma_counts.py
"""Tests for PRISMA flow count computation."""
import pytest
from tests.conftest import SAMPLE_PAPER


def test_prisma_counts_empty_review(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    review = rm.create_review("Empty", "No searches yet")
    counts = rm.prisma_counts(review["id"])
    assert counts["identification"]["total_records"] == 0
    assert counts["duplicates_removed"] == 0
    assert counts["unique_records"] == 0
    assert counts["included"] == 0


def test_prisma_counts_with_data(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    review = rm.create_review("Test SR", "Testing PRISMA")
    rid = review["id"]

    # Simulate two searches
    sid1 = rm.log_search(rid, "pubmed", "query1", {}, raw_count=100, new_count=80)
    sid2 = rm.log_search(rid, "openalex", "query2", {}, raw_count=60, new_count=30)

    # Add papers
    papers = [
        {"title": f"Paper {i}", "authors": [f"Author {i}"], "year": 2024,
         "doi": f"10.1234/test.{i}", "pmid": None, "source": "pubmed"}
        for i in range(110)
    ]
    rm.add_papers(rid, sid1, papers[:80], "pubmed")
    rm.add_papers(rid, sid2, papers[70:100], "openalex")  # 10 overlap by DOI

    # Screen some
    all_papers = rm.get_review_papers(rid, limit=200)
    screen_out = [p["id"] for p in all_papers[:70]]
    screen_in = [p["id"] for p in all_papers[70:90]]
    include = [p["id"] for p in all_papers[90:100]]

    rm.update_paper_status(rid, screen_out, "screened_out")
    rm.update_paper_status(rid, screen_in, "screened_in")
    rm.update_paper_status(rid, include, "included")

    counts = rm.prisma_counts(rid)

    assert counts["identification"]["total_records"] == 160  # 100 + 60
    assert counts["identification"]["databases"]["pubmed"]["searches"] == 1
    assert counts["identification"]["databases"]["pubmed"]["records"] == 100
    assert counts["identification"]["databases"]["openalex"]["searches"] == 1
    assert counts["identification"]["databases"]["openalex"]["records"] == 60
    assert counts["unique_records"] == 100  # 80 + 30 = 110 minus 10 DOI dupes = 100
    assert counts["duplicates_removed"] == 60  # 160 raw - 100 unique
    assert counts["screening"]["screened_out"] == 70
    assert counts["screening"]["sought_for_retrieval"] == 20
    assert counts["included"] == 10


def test_prisma_counts_not_found(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    result = rm.prisma_counts("nonexistent-id")
    assert "error" in result


def test_prisma_counts_with_snowball(tmp_db_dir):
    import review_manager as rm
    rm._ensure_tables()
    review = rm.create_review("Test SR", "Testing")
    rid = review["id"]

    rm.log_search(rid, "pubmed", "query1", {}, raw_count=50, new_count=50)
    rm.log_search(rid, "snowball", '["DOI:10.1234"]', {"direction": "both"}, raw_count=200, new_count=80)

    counts = rm.prisma_counts(rid)
    assert "snowball" in counts["identification"]["other_methods"]
    assert counts["identification"]["other_methods"]["snowball"]["records"] == 200
    assert counts["identification"]["databases"]["pubmed"]["records"] == 50
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -m pytest tests/test_prisma_counts.py -v`
Expected: 4 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_prisma_counts.py
git commit -m "test: add PRISMA flow count tests"
```

---

## Task 5: Integrate PubMed into orchestrator

**Files:**
- Modify: `orchestrator.py`

- [ ] **Step 1: Add pubmed to `_query_source`**

In `orchestrator.py`, add a new `elif` block in `_query_source` (after the `medrxiv` block, around line 400):

```python
    elif source == "pubmed":
        result = pubmed_client.search_pubmed(query, max_results=num_results)
        return result.get("papers", [])
```

Add the import at the top of `orchestrator.py` (after the existing client imports around line 23):

```python
import pubmed_client
```

- [ ] **Step 2: Add pubmed to `smart_search` default source list**

In `orchestrator.py`, in the `smart_search` function (around line 73-77), modify the default source list:

Change:
```python
    if sources is None:
        sources = ["openalex", "s2"]
        if include_preprints:
            sources.extend(["arxiv", "medrxiv"])
        sources.append("crossref")
```

To:
```python
    if sources is None:
        sources = ["openalex"]
        if _has_medical_terms(query):
            sources.append("pubmed")
        sources.append("s2")
        if include_preprints:
            sources.extend(["arxiv", "medrxiv"])
        sources.append("crossref")
```

- [ ] **Step 3: Smoke test the integration**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -c "import orchestrator; print(orchestrator._query_source('pubmed', 'gastric cancer', 5, None))"`
Expected: Returns a list of paper dicts from PubMed (or an error if no network — that's fine, the integration path is correct)

- [ ] **Step 4: Commit**

```bash
git add orchestrator.py
git commit -m "feat: integrate PubMed into orchestrator

PubMed added to smart_search (after OpenAlex, medical queries only)
and available as source in _query_source."
```

---

## Task 6: Add snowball search to orchestrator

**Files:**
- Modify: `orchestrator.py`
- Create: `tests/test_snowball.py`

- [ ] **Step 1: Write failing tests for snowball logic**

```python
# tests/test_snowball.py
"""Tests for snowball search logic."""
from unittest.mock import patch, MagicMock
import pytest
from tests.conftest import SAMPLE_PAPER


def _make_citation(i: int, doi_prefix: str = "10.9999/cite") -> dict:
    return {
        "title": f"Citing paper {i}",
        "authors": [f"Citer {i}"],
        "year": 2024,
        "doi": f"{doi_prefix}.{i}",
        "pmid": None,
        "citationCount": 5,
    }


def _make_reference(i: int, doi_prefix: str = "10.9999/ref") -> dict:
    return {
        "title": f"Referenced paper {i}",
        "authors": [f"Author {i}"],
        "year": 2020,
        "doi": f"{doi_prefix}.{i}",
        "pmid": None,
        "citationCount": 20,
    }


@patch("semantic_scholar_client.get_paper_citations")
@patch("semantic_scholar_client.get_paper_references")
def test_snowball_both_directions(mock_refs, mock_cites, tmp_db_dir):
    mock_cites.return_value = [_make_citation(i) for i in range(5)]
    mock_refs.return_value = [_make_reference(i) for i in range(3)]

    import review_manager as rm
    import orchestrator
    rm._ensure_tables()
    review = rm.create_review("Test", "Test")
    rid = review["id"]

    result = orchestrator.snowball_search(rid, ["DOI:10.1234/seed.1"], direction="both")

    assert result["seed_count"] == 1
    assert result["total_harvested"] == 8  # 5 citations + 3 references
    assert result["new_candidates_added"] == 8
    assert "search_id" in result


@patch("semantic_scholar_client.get_paper_citations")
@patch("semantic_scholar_client.get_paper_references")
def test_snowball_deduplicates_across_seeds(mock_refs, mock_cites, tmp_db_dir):
    # Both seeds cite the same paper
    shared = _make_citation(99, "10.9999/shared")
    mock_cites.side_effect = [
        [_make_citation(1), shared],
        [_make_citation(2), shared],
    ]
    mock_refs.return_value = []

    import review_manager as rm
    import orchestrator
    rm._ensure_tables()
    review = rm.create_review("Test", "Test")
    rid = review["id"]

    result = orchestrator.snowball_search(rid, ["DOI:10.1234/seed.1", "DOI:10.1234/seed.2"], direction="forward")

    assert result["total_harvested"] == 4  # 2 + 2
    assert result["duplicates_within_snowball"] == 1  # shared paper
    assert result["new_candidates_added"] == 3  # 4 - 1 duplicate


@patch("semantic_scholar_client.get_paper_citations")
@patch("semantic_scholar_client.get_paper_references")
def test_snowball_deduplicates_against_review(mock_refs, mock_cites, tmp_db_dir):
    mock_cites.return_value = [_make_citation(1)]
    mock_refs.return_value = []

    import review_manager as rm
    import orchestrator
    rm._ensure_tables()
    review = rm.create_review("Test", "Test")
    rid = review["id"]

    # Pre-populate review with the same paper
    existing = _make_citation(1)
    rm.add_papers(rid, "prev-search", [existing], "s2")

    result = orchestrator.snowball_search(rid, ["DOI:10.1234/seed.1"], direction="forward")

    assert result["total_harvested"] == 1
    assert result["duplicates_against_review"] == 1
    assert result["new_candidates_added"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -m pytest tests/test_snowball.py -v`
Expected: FAIL — `AttributeError: module 'orchestrator' has no attribute 'snowball_search'`

- [ ] **Step 3: Implement `snowball_search` in `orchestrator.py`**

Add at the bottom of `orchestrator.py`, before any `if __name__` block:

```python
import review_manager


def snowball_search(
    review_id: str,
    seed_paper_ids: List[str],
    direction: str = "both",
) -> Dict[str, Any]:
    """
    Harvest citations and/or references from seed papers, deduplicate
    against the review library, and add new candidates.

    Parameters:
        review_id: Review to add candidates to.
        seed_paper_ids: List of DOIs or S2 IDs (max 50).
        direction: "forward" (citations), "backward" (references), or "both".

    Returns:
        Summary dict with counts.
    """
    if len(seed_paper_ids) > 50:
        return {"error": "Maximum 50 seed papers per snowball search."}

    all_candidates = []
    has_api_key = bool(http_client.get_env("S2_API_KEY"))
    delay = 0.01 if has_api_key else 1.0

    for seed_id in seed_paper_ids:
        if direction in ("forward", "both"):
            try:
                citations = s2.get_paper_citations(seed_id, num_results=100)
                all_candidates.extend(citations)
            except Exception as e:
                logger.warning(f"Snowball citations failed for {seed_id}: {e}")

        if direction in ("backward", "both"):
            try:
                references = s2.get_paper_references(seed_id, num_results=100)
                all_candidates.extend(references)
            except Exception as e:
                logger.warning(f"Snowball references failed for {seed_id}: {e}")

        import time
        time.sleep(delay)

    total_harvested = len(all_candidates)

    # Deduplicate within snowball results
    deduped = _deduplicate(all_candidates)
    duplicates_within = total_harvested - len(deduped)

    # Deduplicate against review library
    new_papers = []
    duplicates_against_review = 0
    for paper in deduped:
        if review_manager.is_duplicate(review_id, paper):
            duplicates_against_review += 1
        else:
            new_papers.append(paper)

    # Log the search
    search_id = review_manager.log_search(
        review_id,
        source="snowball",
        query=json.dumps(seed_paper_ids),
        filters={"direction": direction},
        raw_count=total_harvested,
        new_count=len(new_papers),
    )

    # Add new papers
    if new_papers:
        review_manager.add_papers(review_id, search_id, new_papers, "snowball")

    return {
        "seed_count": len(seed_paper_ids),
        "total_harvested": total_harvested,
        "duplicates_within_snowball": duplicates_within,
        "duplicates_against_review": duplicates_against_review,
        "new_candidates_added": len(new_papers),
        "search_id": search_id,
    }
```

Also add `import json` and `import http_client` at the top of `orchestrator.py` if not already imported.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -m pytest tests/test_snowball.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add orchestrator.py tests/test_snowball.py
git commit -m "feat: add snowball search to orchestrator

Harvests citations/references from seed papers via S2, deduplicates
within snowball and against review library, logs to review."
```

---

## Task 7: Add new tools to server.py

**Files:**
- Modify: `server.py`

- [ ] **Step 1: Add imports to server.py**

At the top of `server.py`, add after existing imports (around line 43):

```python
import pubmed_client
import review_manager
```

- [ ] **Step 2: Add `pubmed_search` tool**

Add after the `search_papers` tool block (around line 372):

```python
@mcp.tool()
async def pubmed_search(
    query: str,
    max_results: int = 100,
) -> Dict[str, Any]:
    """
    Search PubMed using full NCBI E-utilities syntax. Use this for structured
    systematic review search strategies with MeSH terms, Boolean operators,
    and field tags.

    Examples:
      - "intestinal metaplasia"[MeSH] AND "deep learning"[ti]
      - ("Barrett esophagus"[MeSH] OR "gastric cancer"[MeSH]) AND "artificial intelligence"[ti]
      - "Soroush A"[au] AND "endoscopy"[mh]

    For simple keyword searches, use search_papers(source="pubmed") instead.

    Args:
        query: PubMed query string (full E-utilities syntax)
        max_results: Maximum results (default: 100, max: 10000)
    """
    max_results = _clamp(max_results, 1, 10000)
    logger.info(f"PubMed search: {_log_query(query)}")
    try:
        result = await asyncio.to_thread(pubmed_client.search_pubmed, query, max_results)
        # Auto-log to active review
        active_rid = review_manager.get_active_review()
        if active_rid and result.get("papers"):
            search_id = review_manager.log_search(
                active_rid, "pubmed", query, {"max_results": max_results},
                raw_count=len(result["papers"]), new_count=0,
            )
            new_count = review_manager.add_papers(active_rid, search_id, result["papers"], "pubmed")
            # Update the log with actual new count
            review_manager.update_search_new_count(search_id, new_count)
            result["review_new_papers"] = new_count
        return result
    except Exception as e:
        return _error_dict(f"PubMed search failed: {str(e)}")
```

- [ ] **Step 3: Add `source="pubmed"` to `search_papers`**

In the `search_papers` tool, add a new `elif` block after the `google_scholar` block (around line 362):

```python
        elif source == "pubmed":
            result = await asyncio.to_thread(
                pubmed_client.search_pubmed, query, min(num_results, 10000)
            )
            results = result.get("papers", [])
```

- [ ] **Step 4: Add review management tools**

Add after the cache tools section:

```python
# ============================================================================
# SYSTEMATIC REVIEW TOOLS
# ============================================================================


@mcp.tool()
async def create_review(name: str, query_description: str = "") -> Dict[str, Any]:
    """
    Create a new systematic review. This is the first step in a PRISMA-compliant
    review workflow. After creating, use set_active_review to enable auto-logging.

    Args:
        name: Short name for the review (e.g., "GIM risk stratification SR")
        query_description: The research question or PICO statement
    """
    logger.info(f"Create review: {name}")
    try:
        return await asyncio.to_thread(review_manager.create_review, name, query_description)
    except Exception as e:
        return _error_dict(f"Create review failed: {str(e)}")


@mcp.tool()
async def list_reviews() -> List[Dict[str, Any]]:
    """List all systematic reviews with paper counts."""
    try:
        return await asyncio.to_thread(review_manager.list_reviews)
    except Exception as e:
        return _error_list(f"List reviews failed: {str(e)}")


@mcp.tool()
async def get_review(review_id: str) -> Dict[str, Any]:
    """
    Get full review details: search log, paper counts by screening status.

    Args:
        review_id: Review UUID
    """
    try:
        return await asyncio.to_thread(review_manager.get_review, review_id)
    except Exception as e:
        return _error_dict(f"Get review failed: {str(e)}")


@mcp.tool()
async def set_active_review(review_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Set the active review for auto-logging. When active, all searches
    (smart_search, search_papers, pubmed_search) automatically log results
    and deduplicate against this review's paper library.

    Pass null/None to deactivate.

    Args:
        review_id: Review UUID to activate, or null to deactivate
    """
    logger.info(f"Set active review: {review_id}")
    return review_manager.set_active_review(review_id)


@mcp.tool()
async def update_paper_status(
    review_id: str,
    paper_ids: List[str],
    status: str,
) -> Dict[str, Any]:
    """
    Batch update screening status for papers in a review.

    Args:
        review_id: Review UUID
        paper_ids: List of paper UUIDs to update
        status: New status — "new", "screened_in", "screened_out", or "included"
    """
    valid = {"new", "screened_in", "screened_out", "included"}
    if status not in valid:
        return _error_dict(f"Invalid status: '{status}'. Options: {', '.join(sorted(valid))}")
    logger.info(f"Update {len(paper_ids)} papers to '{status}' in review {review_id}")
    try:
        count = await asyncio.to_thread(review_manager.update_paper_status, review_id, paper_ids, status)
        return {"updated": count, "status": status}
    except Exception as e:
        return _error_dict(f"Update paper status failed: {str(e)}")


@mcp.tool()
async def get_review_papers(
    review_id: str,
    status_filter: Optional[str] = None,
    search_id: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Get paginated papers from a review, optionally filtered by status or search.

    Args:
        review_id: Review UUID
        status_filter: Filter by status ("new", "screened_in", "screened_out", "included")
        search_id: Filter by search UUID (e.g., to see snowball results)
        offset: Pagination offset (default: 0)
        limit: Page size (default: 50, max: 200)
    """
    limit = _clamp(limit, 1, 200)
    try:
        return await asyncio.to_thread(
            review_manager.get_review_papers, review_id, status_filter, search_id, offset, limit
        )
    except Exception as e:
        return _error_list(f"Get review papers failed: {str(e)}")


@mcp.tool()
async def snowball_search(
    review_id: str,
    seed_paper_ids: List[str],
    direction: str = "both",
) -> Dict[str, Any]:
    """
    Harvest citations and/or references from seed papers, deduplicate against
    the review library, and add new candidates. Use this for forward/backward
    reference searching in systematic reviews.

    Args:
        review_id: Review UUID to add candidates to
        seed_paper_ids: List of DOIs or S2 paper IDs (max 50)
        direction: "forward" (who cited these), "backward" (what these cite), or "both"
    """
    if len(seed_paper_ids) > 50:
        return _error_dict("Maximum 50 seed papers per snowball search.")
    if direction not in ("forward", "backward", "both"):
        return _error_dict(f"Invalid direction: '{direction}'. Options: forward, backward, both")
    logger.info(f"Snowball search: {len(seed_paper_ids)} seeds, direction={direction}")
    try:
        return await asyncio.to_thread(orchestrator.snowball_search, review_id, seed_paper_ids, direction)
    except Exception as e:
        return _error_dict(f"Snowball search failed: {str(e)}")


@mcp.tool()
async def export_review(
    review_id: str,
    status_filter: str = "all",
    format: str = "dois",
) -> Dict[str, Any]:
    """
    Export papers from a review for Zotero import or other tools.
    Returns DOIs (for Zotero create_item_from_identifier) or full paper dicts.

    Args:
        review_id: Review UUID
        status_filter: "all", "new", "screened_in", "screened_out", or "included"
        format: "dois" (list of DOI strings) or "full" (full paper dicts)
    """
    logger.info(f"Export review {review_id}: filter={status_filter}, format={format}")
    try:
        sf = None if status_filter == "all" else status_filter
        papers = await asyncio.to_thread(
            review_manager.get_review_papers, review_id, sf, None, 0, 10000
        )
        if format == "dois":
            dois = [p["doi"] for p in papers if p.get("doi")]
            return {"review_id": review_id, "count": len(dois), "dois": dois}
        else:
            return {"review_id": review_id, "count": len(papers), "papers": papers}
    except Exception as e:
        return _error_dict(f"Export review failed: {str(e)}")


@mcp.tool()
async def prisma_counts(review_id: str) -> Dict[str, Any]:
    """
    Get PRISMA 2020 flow diagram counts for a review. Returns identification
    (records per database), duplicates removed, screening counts, and included.

    Args:
        review_id: Review UUID
    """
    logger.info(f"PRISMA counts for review {review_id}")
    try:
        return await asyncio.to_thread(review_manager.prisma_counts, review_id)
    except Exception as e:
        return _error_dict(f"PRISMA counts failed: {str(e)}")
```

- [ ] **Step 5: Add auto-logging hooks to existing search tools**

In the `smart_search` tool (around line 205-220), add after the `result = await asyncio.to_thread(...)` line and before the return:

```python
        # Auto-log to active review
        active_rid = review_manager.get_active_review()
        if active_rid and result.get("results"):
            search_id = review_manager.log_search(
                active_rid, "smart_search", query,
                {"year": year, "sources_queried": result.get("sources_queried", [])},
                raw_count=result.get("total_raw", 0), new_count=0,
            )
            new_count = review_manager.add_papers(
                active_rid, search_id, result["results"], "smart_search"
            )
            review_manager.update_search_new_count(search_id, new_count)
            result["review_new_papers"] = new_count
```

In the `search_papers` tool (around line 368-370), add similarly before the return:

```python
        # Auto-log to active review
        active_rid = review_manager.get_active_review()
        if active_rid and results:
            search_id = review_manager.log_search(
                active_rid, source, query,
                {"year": year, "sort_by": sort_by, "type_filter": type_filter},
                raw_count=len(results), new_count=0,
            )
            new_count = review_manager.add_papers(active_rid, search_id, results, source)
            review_manager.update_search_new_count(search_id, new_count)
```

- [ ] **Step 6: Commit**

```bash
git add server.py
git commit -m "feat: add 10 systematic review tools to server

pubmed_search, create_review, list_reviews, get_review, set_active_review,
update_paper_status, get_review_papers, snowball_search, export_review,
prisma_counts. Auto-logging hooks added to smart_search and search_papers."
```

---

## Task 8: Update server docstring and smoke test

**Files:**
- Modify: `server.py` (docstring only)

- [ ] **Step 1: Update the module docstring**

Replace the docstring at the top of `server.py` (lines 1-26) to reflect the new capabilities:

```python
"""
Academic Research MCP Server

A unified MCP server providing access to eight academic research APIs,
a systematic review library, and PRISMA-compliant workflow tools:

  Search Sources:
  1. Google Scholar -- keyword search, advanced search, author profiles
  2. ORCID -- researcher profiles, publications, employment, education, funding
  3. Semantic Scholar -- paper search, citation graphs, author metrics, recommendations, batch lookup
  4. arXiv -- CS/ML preprints, search by author/title/category, full metadata
  5. medRxiv/bioRxiv -- health sciences preprints, publication status tracking
  6. OpenAlex -- 250M+ works, highest throughput, no auth needed
  7. CrossRef -- DOI registry fallback, 50 req/sec, comprehensive metadata
  8. PubMed -- NCBI E-utilities, MeSH terms, Boolean queries, field tags
  9. Unpaywall -- legal open access PDF resolution for any DOI

  Systematic Review Tools:
  - Review library with persistent state (SQLite)
  - Paper deduplication (DOI, PMID, fuzzy title)
  - Auto-logged search strategies
  - Snowball search (forward/backward citation harvesting)
  - PRISMA 2020 flow counts
  - Export for Zotero integration

Features:
  - Consolidated tool surface (~28 tools)
  - Local SQLite cache with singleton connection and WAL mode
  - S2 batch endpoint for up to 500 papers in one request
  - CrossRef fallback when other APIs are rate-limited

No API keys required for basic use. Optional env vars:
  - S2_API_KEY: Higher Semantic Scholar rate limits
  - OPENALEX_EMAIL: OpenAlex polite pool (10 req/sec vs 1 req/sec)
  - CROSSREF_EMAIL: CrossRef polite pool (50 req/sec)
  - NCBI_API_KEY: Higher PubMed rate limits (10 req/sec vs 3 req/sec)
"""
```

- [ ] **Step 2: Run full test suite**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Smoke test server startup**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && timeout 5 ./venv/bin/python server.py 2>&1 || true`
Expected: Server starts without import errors (will timeout after 5s since it's a long-running server — that's fine)

- [ ] **Step 4: Commit**

```bash
git add server.py
git commit -m "docs: update server docstring for new systematic review capabilities"
```

---

## Task 9: Install pytest if needed and run full validation

- [ ] **Step 1: Ensure pytest is available**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -m pytest --version 2>&1 || ./venv/bin/pip install pytest`

- [ ] **Step 2: Run complete test suite**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 3: Verify import chain works**

Run: `cd /Users/ali.soroush/Library/CloudStorage/OneDrive-Personal/Desktop/experiment/academic-research-mcp && ./venv/bin/python -c "import server; print(f'Tools registered: {len(server.mcp._tool_manager._tools)}')"`
Expected: Prints approximately "Tools registered: 28"
