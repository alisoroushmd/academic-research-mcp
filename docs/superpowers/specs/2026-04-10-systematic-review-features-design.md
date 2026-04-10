# Systematic Review Features for Academic Research MCP

**Date:** 2026-04-10
**Status:** Draft
**Scope:** 6 features to extend the academic-research MCP from a literature discovery tool into a systematic review support tool

## Overview

Add a review-centric state model, PubMed/NCBI E-utilities connector, snowball search, Zotero export, auto-logged search strategies, and PRISMA flow counts. All features organized around a persistent review library stored in the existing SQLite database.

## Architecture Decision

**Approach: Review-Centric.** A stateful review library is the central concept. Searches auto-log when a review is active, deduplication runs against the review's accumulated papers, and PRISMA counts read from review state. This avoids reimplementing "which papers have I already seen" in every tool independently.

## Current Architecture (for context)

- **Framework:** FastMCP (`mcp.server.fastmcp`)
- **Server:** `server.py` (~900 lines) — tool definitions, compact output mode, error helpers
- **Orchestrator:** `orchestrator.py` (~525 lines) — `smart_search` (multi-source + dedup + early stopping), `find_paper` (universal resolver)
- **Clients:** 8 modules (`openalex_client.py`, `semantic_scholar_client.py`, `crossref_client.py`, `arxiv_client.py`, `medrxiv_client.py`, `google_scholar_client.py`, `orcid_client.py`, `unpaywall_client.py`)
- **Cache:** `cache.py` — SQLite with WAL mode, singleton connection, thread lock, TTL-based expiry
- **Dependencies:** `requests`, `mcp`, `scholarly`, `httpx[socks]`, `pip-system-certs`
- **Env vars:** `S2_API_KEY`, `OPENALEX_EMAIL`, `CROSSREF_EMAIL` (all optional)

---

## Feature 1: PubMed/NCBI E-utilities Connector

### New file: `pubmed_client.py`

Uses NCBI E-utilities REST API (`eutils.ncbi.nlm.nih.gov/entrez/eutils/`).

**Rate limits:** 3 requests/sec without API key, 10 requests/sec with `NCBI_API_KEY` env var.

### Internal functions

1. **`esearch(query, max_results, use_history=True)`**
   - Sends the raw query string to ESearch endpoint
   - Supports full PubMed syntax: MeSH terms (`"intestinal metaplasia"[MeSH]`), Boolean operators (`AND`, `OR`, `NOT`), field tags (`[ti]`, `[au]`, `[pt]`, `[dp]`, `[mh]`)
   - Returns PMIDs + WebEnv/QueryKey for history server pagination
   - Parameters: `db="pubmed"`, `retmode="json"`, `usehistory="y"`

2. **`efetch(pmids_or_webenv, rettype="xml")`**
   - Fetches full article metadata for a list of PMIDs (or via WebEnv for large sets)
   - Parses XML into standardized paper dicts with fields: `title`, `authors` (list), `abstract`, `doi`, `pmid`, `year`, `journal`, `mesh_headings` (list), `publication_types` (list), `volume`, `issue`, `pages`
   - Output format matches existing `_compact_paper` contract (title, authors, year, doi, citation_count, abstract, open_access_url)

3. **`search_pubmed(query, max_results=100)`**
   - Convenience wrapper: esearch -> efetch
   - This is what `search_papers(source="pubmed")` calls

### Integration points

- **`search_papers` tool:** New `source="pubmed"` option routes to `pubmed_client.search_pubmed`. Accepts keyword queries or full Boolean strings.
- **Dedicated `pubmed_search` tool:** For structured SR search strategies. Accepts:
  - `query` (str): Raw PubMed query string with full E-utilities syntax
  - `max_results` (int): Default 100, max 10000
  - Returns paper list + `search_translation` (PubMed's interpretation of the query) + `total_count` (total matching records in PubMed)
- **`smart_search` integration:** PubMed added to source list after OpenAlex, before S2. Only triggered when query contains medical/biomedical terms (reusing `orchestrator._has_medical_terms`).
- **Auto-logging:** When a review is active, both tools log to `review_searches` and deduplicate against `review_papers`.

### New env var

- `NCBI_API_KEY` (optional): Higher rate limits

### New dependency

- None required. E-utilities returns XML; parse with `xml.etree.ElementTree` (stdlib). HTTP via existing `httpx` or `requests`.

### Not in scope

- MeSH term suggestion/expansion tool (can add later)
- PubMed Central full-text retrieval (can add later)

---

## Feature 2: Review Library (State Model)

### New file: `review_manager.py`

Manages review state in the existing SQLite database. Database access: extract `_get_db()` and `_get_cache_path()` from `cache.py` into a shared `db.py` module that both `cache.py` and `review_manager.py` import. This avoids `review_manager` depending on `cache` internals while keeping a single DB file and connection.

### Database schema

Three new tables:

```sql
CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    query_description TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
    -- status: 'active', 'completed', 'archived'
);

CREATE TABLE IF NOT EXISTS review_papers (
    id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL REFERENCES reviews(id),
    doi TEXT,
    pmid TEXT,
    title TEXT NOT NULL,
    authors TEXT,          -- JSON array
    year INTEGER,
    source TEXT NOT NULL,  -- which API found it
    search_id TEXT REFERENCES review_searches(id),
    added_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    -- status: 'new', 'screened_in', 'screened_out', 'included'
    metadata TEXT           -- full paper dict as JSON
);

CREATE INDEX IF NOT EXISTS idx_review_papers_review
    ON review_papers(review_id);
CREATE INDEX IF NOT EXISTS idx_review_papers_doi
    ON review_papers(doi);
CREATE INDEX IF NOT EXISTS idx_review_papers_pmid
    ON review_papers(pmid);
CREATE INDEX IF NOT EXISTS idx_review_papers_status
    ON review_papers(review_id, status);

CREATE TABLE IF NOT EXISTS review_searches (
    id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL REFERENCES reviews(id),
    source TEXT NOT NULL,
    query TEXT NOT NULL,
    filters TEXT,           -- JSON blob (year, MeSH, field tags, etc.)
    executed_at REAL NOT NULL,
    result_count_raw INTEGER NOT NULL,
    result_count_new INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_review_searches_review
    ON review_searches(review_id);
```

### Deduplication logic

When adding papers to a review, check for duplicates in this order:

1. **Exact DOI match** (case-insensitive, after stripping `https://doi.org/` prefix)
2. **Exact PMID match**
3. **Fuzzy title match** using `orchestrator._title_similarity` with threshold >= 0.85

Duplicates are silently skipped. The `review_searches` entry still records `result_count_raw` (before dedup) so PRISMA numbers reflect the true retrieval count.

### Internal functions

- `create_review(name, query_description)` -> review dict
- `list_reviews()` -> list of review dicts with paper counts
- `get_review(review_id)` -> full review with search log and paper counts by status
- `add_papers(review_id, search_id, papers, source)` -> count of new papers added
- `is_duplicate(review_id, paper)` -> bool
- `log_search(review_id, source, query, filters, raw_count, new_count)` -> search_id
- `update_paper_status(review_id, paper_ids, status)` -> count updated
- `get_review_papers(review_id, status_filter, search_id, offset, limit)` -> paginated paper list

### Active review (in-memory state)

`set_active_review(review_id)` stores the active review ID in a module-level variable. Resets on server restart. When set, search tools in `server.py` check this and auto-log + auto-deduplicate. Validates that the review ID exists in the database; returns an error if not found.

### Tools exposed in server.py

| Tool | Args | Returns |
|------|------|---------|
| `create_review` | `name`, `query_description` | Review dict with ID |
| `list_reviews` | — | List of reviews with paper counts |
| `get_review` | `review_id` | Full review status, search log, paper counts by status |
| `set_active_review` | `review_id` (or null to deactivate) | Confirmation |
| `update_paper_status` | `review_id`, `paper_ids` (list), `status` | Count updated |
| `get_review_papers` | `review_id`, `status_filter` (optional), `search_id` (optional), `offset` (default 0), `limit` (default 50) | Paginated paper list |

---

## Feature 3: Snowball Search

### Location: `orchestrator.py` (logic) + `server.py` (tool)

### Tool: `snowball_search(review_id, seed_paper_ids, direction="both")`

**Args:**
- `review_id` (str): Which review to add candidates to
- `seed_paper_ids` (list, max 50): DOIs or S2 IDs of seed papers
- `direction` (str): `"forward"` (citations), `"backward"` (references), or `"both"`

**Process:**
1. For each seed paper, call `s2.get_paper_citations` (if forward/both) and `s2.get_paper_references` (if backward/both) with max 100 results each
2. Collect all candidates into a flat list
3. Deduplicate internally (same paper cited by multiple seeds)
4. Deduplicate against the review library via `review_manager.is_duplicate`
5. Add new candidates to `review_papers` via `review_manager.add_papers`
6. Log to `review_searches` with `source="snowball"`, `query` = JSON list of seed IDs, `filters` = `{"direction": direction}`

**Returns:**
```python
{
    "seed_count": 5,
    "total_harvested": 847,
    "duplicates_within_snowball": 203,
    "duplicates_against_review": 312,
    "new_candidates_added": 332,
    "search_id": "abc123"  # for paginating results via get_review_papers
}
```

**Rate limiting:** Semantic Scholar allows 1 request/sec without API key, 100/sec with key. The existing `S2_API_KEY` env var (already configured) is used automatically. With 50 seeds x 2 directions = 100 API calls at 100/sec, this completes in ~1-2 seconds with the key. Without a key, ~2 minutes. Calls run sequentially with appropriate delays based on whether the API key is present.

---

## Feature 4: Zotero Export

### Location: `server.py` (tool only)

### Tool: `export_review(review_id, status_filter="all", format="dois")`

**Args:**
- `review_id` (str): Review to export from
- `status_filter` (str): `"all"`, `"new"`, `"screened_in"`, `"screened_out"`, `"included"`
- `format` (str): `"dois"` (list of DOI strings) or `"full"` (full paper dicts)

**Returns:** List of DOIs or paper dicts, filtered by status.

**Usage pattern:** The LLM calls `export_review` to get DOIs, then calls the Zotero MCP's `create_item_from_identifier` for each DOI. No cross-MCP coupling, no new dependencies.

This deliberately does not call Zotero directly. The Zotero MCP already handles collection creation and item creation. The LLM bridges the two MCPs.

---

## Feature 5: Search Strategy Logging (Auto-integrated)

### Location: Integrated into `review_manager.py` and `server.py`

No new tool. When a review is active (via `set_active_review`), the following tools auto-log to `review_searches`:

| Tool | Logged source | Query stored | Filters stored |
|------|--------------|--------------|----------------|
| `smart_search` | `"smart_search"` (single entry) | Original query | `{"year": ..., "sources_queried": [...]}` |
| `search_papers` | The specific source | Original query | `{"year": ..., "sort_by": ..., etc.}` |
| `pubmed_search` | `"pubmed"` | Full PubMed query string | `{"max_results": ...}` |
| `snowball_search` | `"snowball"` | JSON list of seed IDs | `{"direction": ...}` |

**Implementation in `server.py`:** After each search tool's success path, check if `review_manager.get_active_review()` returns a review ID. If so:
1. Call `review_manager.add_papers(review_id, search_id, results, source)` — this deduplicates and returns the new count
2. Call `review_manager.log_search(review_id, source, query, filters, raw_count, new_count)`

This adds ~10 lines to each search tool function. No new tool surface area.

---

## Feature 6: PRISMA Flow Counts

### Location: `review_manager.py` (logic) + `server.py` (tool)

### Tool: `prisma_counts(review_id)`

Reads from `review_searches` and `review_papers` to produce PRISMA 2020-aligned counts:

```python
{
    "identification": {
        "databases": {
            "pubmed": {"searches": 3, "records": 842},
            "openalex": {"searches": 2, "records": 615},
            "s2": {"searches": 1, "records": 203},
            "crossref": {"searches": 0, "records": 0},
            "arxiv": {"searches": 0, "records": 0},
            "medrxiv": {"searches": 1, "records": 45}
        },
        "other_methods": {
            "snowball": {"searches": 1, "seed_papers": 5, "records": 327}
        },
        "total_records": 2032
    },
    "duplicates_removed": 659,
    "unique_records": 1373,
    "screening": {
        "screened": 1373,
        "screened_out": 1201,
        "sought_for_retrieval": 172
    },
    "included": 48
}
```

**Data sources:**
- `identification.databases.*`: `SUM(result_count_raw)` from `review_searches` grouped by source
- `identification.other_methods.snowball`: Same, filtered to `source='snowball'`
- `duplicates_removed`: `SUM(result_count_raw) - COUNT(review_papers)` for the review
- `screening.*`: `COUNT` from `review_papers` grouped by status
  - `screened` = total unique papers
  - `screened_out` = status `'screened_out'`
  - `sought_for_retrieval` = status `'screened_in'`
  - `included` = status `'included'`

---

## Summary of Changes

### New files
| File | Purpose | Est. lines |
|------|---------|-----------|
| `db.py` | Shared SQLite connection extracted from `cache.py` | ~50 |
| `pubmed_client.py` | NCBI E-utilities connector | ~200 |
| `review_manager.py` | Review state, dedup, logging, PRISMA counts | ~300 |

### Modified files
| File | Changes |
|------|---------|
| `server.py` | Add ~10 new tools, add auto-logging hooks to existing search tools |
| `orchestrator.py` | Add `snowball_search` function, add `"pubmed"` to `_query_source` and `smart_search` source list |
| `cache.py` | Refactor to import DB connection from `db.py` instead of managing it directly |
| `requirements.txt` | No new dependencies (E-utilities XML parsed with stdlib `xml.etree.ElementTree`) |

### New tools (total: 10)
1. `pubmed_search` — structured PubMed/E-utilities queries
2. `create_review` — start a new systematic review
3. `list_reviews` — list all reviews
4. `get_review` — review status and search log
5. `set_active_review` — activate auto-logging for a review
6. `update_paper_status` — batch screening decisions
7. `get_review_papers` — paginated paper list from a review
8. `snowball_search` — citation/reference harvesting
9. `export_review` — export DOIs/papers for Zotero
10. `prisma_counts` — PRISMA 2020 flow diagram numbers

### New env vars
- `NCBI_API_KEY` (optional): Higher PubMed rate limits (10/sec vs 3/sec)

### Existing tool modifications
- `search_papers`: New `source="pubmed"` option
- `smart_search`: PubMed added to source list (after OpenAlex, before S2, medical queries only)
