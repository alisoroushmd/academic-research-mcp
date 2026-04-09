# Academic Research MCP Server

A unified [Model Context Protocol](https://modelcontextprotocol.io/) server that provides AI assistants with access to seven academic research APIs through **18 consolidated tools**, plus local caching and batch operations. Designed for biomedical researchers who work across clinical medicine and computer science.

## APIs & Tools

| API | Auth | Rate Limit | What it does |
|-----|------|------------|-------------|
| **Google Scholar** | None | ~100 req then CAPTCHA | Keyword search, advanced search, author profiles |
| **ORCID** | None | Unlimited | Researcher profiles, publications, funding |
| **Semantic Scholar** | Optional | 100/5min or 1/sec with key | Paper search, citation graphs, recommendations, batch lookup |
| **arXiv** | None | 1 req/3 sec | CS/ML preprint search with arXiv query syntax |
| **medRxiv/bioRxiv** | None | Reasonable use | Preprint search, date-range browsing, publication status |
| **OpenAlex** | None | 10/sec (polite pool) | 250M+ works, authors, institutions |
| **CrossRef** | None | 50/sec (polite pool) | DOI registry fallback, author search |
| **Unpaywall** | None | 100K/day | Legal open access PDF resolution |

No API keys required. Optional environment variables for higher throughput:

| Variable | Effect |
|----------|--------|
| `S2_API_KEY` | Semantic Scholar: 100/5min -> 1/sec sustained |
| `OPENALEX_EMAIL` | OpenAlex polite pool: 1/sec -> 10/sec |
| `CROSSREF_EMAIL` | CrossRef polite pool: faster responses (falls back to `OPENALEX_EMAIL`) |

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
        "OPENALEX_EMAIL": "your-email@institution.edu"
      }
    }
  }
}
```

Restart Claude Desktop after saving.

## All 18 Tools

### Smart Tools (start here)
- `smart_search` -- **THE recommended search tool.** Multi-source search with deduplication and early stopping.
- `find_paper` -- Universal paper resolver. Accepts any identifier (DOI, PMID, arXiv ID, URL, title).

### Unified Search & Authors
- `search_papers` -- Search any source via `source` param (openalex, s2, crossref, arxiv, medrxiv, google_scholar). Defaults to smart_search.
- `search_authors` -- Search for researchers across openalex, s2, orcid, google_scholar.
- `get_author` -- Detailed author profile by ID (auto-detects source from ID format).
- `get_author_works` -- Publications by author across any source.
- `get_author_funding` -- ORCID funding/grants history.

### Citation & Recommendation (Semantic Scholar)
- `get_paper_citations` -- Forward citation graph (who cited this paper).
- `get_paper_references` -- Backward citation graph (what this paper cites).
- `recommend_papers` -- "Papers like this one" recommendations.
- `batch_get_papers` -- **Batch lookup: up to 500 papers in one request.**

### Preprints (medRxiv/bioRxiv)
- `preprints_by_date` -- Browse preprints by date range.
- `preprint_status` -- Check if a preprint has been journal-published.
- `recent_preprints` -- Recent preprints by subject category.

### Institutions
- `get_institution` -- Institution details from OpenAlex.

### PDF & Open Access
- `find_paper_pdf` -- **Resolve best legal PDF for any DOI** (Unpaywall, PMC, preprints, repositories).
- `batch_check_open_access` -- Check OA status for multiple DOIs (concurrent).

### Cache
- `cache_stats` -- View cache health: entries, size, categories.
- `cache_clear` -- Clear cache (all or by category).

## Abstracts

All search tools return abstracts where available. Semantic Scholar, arXiv, and medRxiv return full abstracts directly. OpenAlex reconstructs abstracts from its inverted index format. CrossRef returns abstracts when publishers deposit them (coverage varies). Use abstract content to assess relevance before fetching full papers.

## When to Use Which Source

| Source | Best for |
|--------|----------|
| **smart_search** | Default -- automatically picks the best sources |
| **Semantic Scholar** | AI/ML papers, citation graphs, influence metrics, batch lookups |
| **OpenAlex** | High-volume searches, comprehensive coverage, no rate limit worries |
| **CrossRef** | Fallback when other APIs throttle, DOI verification, citation counts |
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
4. **Cache hit** -- Repeated lookups (landmark papers, your own work) are instant
5. **Google Scholar last** -- Most aggressive rate limiting, use sparingly

## Local Cache

The server includes a SQLite cache (WAL mode, singleton connection, thread-safe) at `~/.cache/academic-research-mcp/cache.db` that:
- Caches results from all 7 API clients via `@cached` decorator
- Avoids redundant API calls for frequently accessed papers
- Default TTL: 24 hours for searches, 7 days for paper details, 3 days for authors
- Expired entries cleaned up automatically on server startup
- Override location with `ACADEMIC_CACHE_DIR` env var

## Dependencies

- Python 3.10+
- [scholarly](https://github.com/scholarly-python-package/scholarly) -- Google Scholar access
- [mcp](https://github.com/modelcontextprotocol/python-sdk) -- Model Context Protocol SDK
- [requests](https://docs.python-requests.org/) -- HTTP client
- [httpx[socks]](https://www.python-httpx.org/) -- SOCKS proxy support for scholarly

## License

MIT
