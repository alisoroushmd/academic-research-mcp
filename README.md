# Academic Research MCP Server

A unified [Model Context Protocol](https://modelcontextprotocol.io/) server that provides AI assistants with access to nine academic research APIs through **25 tools**, plus local caching, systematic review management, and PRISMA-compliant workflow support. Designed for biomedical researchers who work across clinical medicine and computer science.

## APIs & Data Sources

| API | Auth | Rate Limit | What it does |
|-----|------|------------|-------------|
| **OpenAlex** | None | 10/sec (polite pool) | 250M+ works, authors, institutions |
| **Semantic Scholar** | Optional | 100/5min or 1/sec with key | Paper search, citation graphs, recommendations, batch lookup |
| **CrossRef** | None | 50/sec (polite pool) | DOI registry fallback, author search |
| **PubMed** | Optional | 3/sec or 10/sec with key | NCBI E-utilities, full Boolean/MeSH query syntax |
| **arXiv** | None | 1 req/3 sec | CS/ML preprint search with arXiv query syntax |
| **medRxiv/bioRxiv** | None | Reasonable use | Preprint search, date-range browsing, publication status |
| **Google Scholar** | None | ~100 req then CAPTCHA | Keyword search, advanced search, author profiles |
| **ORCID** | None | Unlimited | Researcher profiles, publications, funding |
| **Unpaywall** | None | 100K/day | Legal open access PDF resolution |

No API keys required for basic use. Optional environment variables for higher throughput:

| Variable | Effect |
|----------|--------|
| `S2_API_KEY` | Semantic Scholar: 100/5min -> 1/sec sustained |
| `OPENALEX_EMAIL` | OpenAlex polite pool: 1/sec -> 10/sec |
| `CROSSREF_EMAIL` | CrossRef polite pool: faster responses (falls back to `OPENALEX_EMAIL`) |
| `NCBI_API_KEY` | PubMed: 3/sec -> 10/sec |

## Quick Start

```bash
git clone https://github.com/alisoroushmd/academic-research-mcp.git
cd academic-research-mcp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py
```

## Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "academic-research": {
      "command": "/path/to/academic-research-mcp/venv/bin/python",
      "args": ["/path/to/academic-research-mcp/server.py"],
      "env": {
        "S2_API_KEY": "your-key-here",
        "OPENALEX_EMAIL": "your-email@institution.edu",
        "NCBI_API_KEY": "your-ncbi-key-here"
      }
    }
  }
}
```

Restart Claude Desktop after saving.

## All 25 Tools

### Smart Tools (start here)
- `smart_search` -- **THE recommended search tool.** Multi-source search with deduplication and early stopping. Auto-logs to active review when set.
- `find_paper` -- Universal paper resolver. Accepts any identifier (DOI, PMID, arXiv ID, URL, title).

### Unified Search & Authors
- `search_papers` -- Search any source via `source` param (openalex, s2, crossref, arxiv, medrxiv, google_scholar, pubmed). For PubMed, supports full MeSH/Boolean syntax. Auto-logs to active review.
- `search_authors` -- Search for researchers across openalex, s2, orcid, google_scholar.
- `get_author` -- Detailed author profile by ID (auto-detects source from ID format).
- `get_author_works` -- Publications by author across any source.
- `get_author_funding` -- ORCID funding/grants history.

### Citation & Recommendation (Semantic Scholar)
- `get_paper_network` -- Citation network: forward (who cited this), backward (what this cites), or both.
- `recommend_papers` -- "Papers like this one" recommendations.
- `batch_get_papers` -- **Batch lookup: up to 500 papers in one request.**

### Preprints (medRxiv/bioRxiv)
- `preprints` -- Three modes: recent (by category), date_range, or publication status check.

### Institutions
- `get_institution` -- Institution details from OpenAlex.

### PDF & Open Access
- `open_access` -- Find legal PDFs for one or multiple DOIs (Unpaywall, PMC, preprints, repositories).

### Citation Validation
- `validate_citations` -- Verify DOIs and PMIDs actually exist before presenting to users (max 25).

### Cache
- `cache_manage` -- View cache stats or clear by category.

### Systematic Review Tools
- `create_review` -- Start a new systematic review with a name and research question.
- `reviews` -- List all reviews or get full details (search log, paper counts by status) for one.
- `delete_review` -- Permanently delete a review and all its data.
- `set_active_review` -- Activate auto-logging: all subsequent searches auto-deduplicate and log to this review.
- `add_papers_to_review` -- Manually add papers by DOI/PMID (for expert recommendations, reference lists).
- `get_review_papers` -- Paginated retrieval with optional status/search filters.
- `update_paper_status` -- Batch update screening status (new, screened_in, screened_out, included).
- `snowball_search` -- Citation harvesting: forward/backward from seed papers, deduplicated against the review library.
- `export_review` -- Export papers as DOI list or full dicts for Zotero import.
- `prisma_counts` -- PRISMA 2020 flow diagram counts (identification, screening, included).

## Systematic Review Workflow

```
1. create_review("GIM risk SR", "gastric intestinal metaplasia risk stratification")
2. set_active_review(review_id)       # enables auto-logging
3. smart_search / search_papers       # results auto-deduplicate and log
4. snowball_search(review_id, seeds)  # citation harvesting from key papers
5. add_papers_to_review(review_id, ["10.xxxx/..."])  # manual additions
6. get_review_papers(review_id)       # browse candidates
7. update_paper_status(review_id, paper_ids, "screened_in")
8. prisma_counts(review_id)           # PRISMA flow diagram numbers
9. export_review(review_id)           # DOI list for Zotero import
```

All searches are logged with source, query, filters, raw count, and new-after-dedup count. Deduplication uses DOI (case-insensitive), PMID, and fuzzy title matching (>=85% similarity).

## Abstracts

All search tools return abstracts where available. Semantic Scholar, arXiv, PubMed, and medRxiv return full abstracts directly. OpenAlex reconstructs abstracts from its inverted index format. CrossRef returns abstracts when publishers deposit them (coverage varies). Use abstract content to assess relevance before fetching full papers.

## When to Use Which Source

| Source | Best for |
|--------|----------|
| **smart_search** | Default -- automatically picks the best sources |
| **Semantic Scholar** | AI/ML papers, citation graphs, influence metrics, batch lookups |
| **OpenAlex** | High-volume searches, comprehensive coverage, no rate limit worries |
| **CrossRef** | Fallback when other APIs throttle, DOI verification, citation counts |
| **PubMed** | Clinical/biomedical literature, MeSH terms, Boolean queries, field tags |
| **arXiv** | CS/ML preprints before journal publication |
| **medRxiv/bioRxiv** | Health sciences preprints, tracking publication status |
| **Google Scholar** | Catch-all, books, theses, non-indexed sources |
| **ORCID** | Researcher profiles, collaborator lookup, funding history |
| **Unpaywall** | Finding legal free PDFs, checking OA status before paywall |

### Throughput Strategy

When you need to process papers faster than individual APIs allow:

1. **Use smart_search** -- automatically picks OpenAlex first (10 req/sec), adds sources as needed
2. **S2 batch endpoint** -- 500 papers in a single request via `batch_get_papers`
3. **CrossRef fallback** -- 50 req/sec with email, 150M+ works
4. **PubMed** -- 10 req/sec with NCBI API key, full MeSH vocabulary
5. **Cache hit** -- Repeated lookups (landmark papers, your own work) are instant
6. **Google Scholar last** -- Most aggressive rate limiting, use sparingly

## Local Cache

The server includes a SQLite cache (WAL mode, singleton connection, thread-safe) at `~/.cache/academic-research-mcp/cache.db` that:
- Caches results from all 9 API clients via `@cached` decorator
- Avoids redundant API calls for frequently accessed papers
- Default TTL: 24 hours for searches, 7 days for paper details, 3 days for authors
- Expired entries cleaned up automatically on server startup
- Override location with `ACADEMIC_CACHE_DIR` env var

The same database stores systematic review state (reviews, papers, searches) in separate tables.

## Dependencies

- Python 3.10+
- [scholarly](https://github.com/scholarly-python-package/scholarly) -- Google Scholar access
- [mcp](https://github.com/modelcontextprotocol/python-sdk) -- Model Context Protocol SDK
- [requests](https://docs.python-requests.org/) -- HTTP client
- [httpx[socks]](https://www.python-httpx.org/) -- SOCKS proxy support for scholarly

## License

MIT
