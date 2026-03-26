# Academic Research MCP Server

A unified [Model Context Protocol](https://modelcontextprotocol.io/) server that provides AI assistants with access to seven academic research APIs through **36 tools**, plus local caching and batch operations. Designed for biomedical researchers who work across clinical medicine and computer science.

## APIs & Tools

| API | Tools | Auth | Rate Limit | What it does |
|-----|-------|------|------------|-------------|
| **Google Scholar** | 3 | None | ~100 req then CAPTCHA | Keyword search, advanced search (author + year filters), author profiles |
| **ORCID** | 4 | None | Unlimited | Researcher search, full profiles, publication lists, funding history |
| **Semantic Scholar** | 9 | Optional | 100/5min or 1/sec with key | Paper search, citation graphs, author metrics, recommendations, batch lookup |
| **arXiv** | 3 | None | 1 req/3 sec | CS/ML preprint search with arXiv query syntax, paper lookup, author papers |
| **medRxiv/bioRxiv** | 5 | None | Reasonable use | Preprint search, date-range browsing, publication status tracking |
| **OpenAlex** | 6 | None | 10/sec (polite pool) | 250M+ works, authors, institutions — highest throughput |
| **CrossRef** | 3 | None | 50/sec (polite pool) | DOI registry fallback, author search, citation counts |
| **Cache** | 2 | N/A | N/A | Local SQLite cache stats and management |

No API keys required. Optional environment variables for higher throughput:

| Variable | Effect |
|----------|--------|
| `S2_API_KEY` | Semantic Scholar: 100/5min → 1/sec sustained |
| `OPENALEX_EMAIL` | OpenAlex polite pool: 1/sec → 10/sec |
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

## All 36 Tools

### Google Scholar
- `google_scholar_search_keywords` — Search by keywords
- `google_scholar_search_advanced` — Filter by author and year range
- `google_scholar_author` — Author profile (h-index, interests, top papers)

### ORCID
- `orcid_search` — Search researchers by name or affiliation
- `orcid_profile` — Full profile: bio, employment, education, keywords
- `orcid_works` — Publications with DOIs and PMIDs
- `orcid_funding` — Grants and funding history

### Semantic Scholar
- `s2_search_papers` — Paper search with year/field/open-access filters
- `s2_paper_details` — Full details, TLDR, references, and citations
- `s2_paper_citations` — Forward citation graph
- `s2_paper_references` — Backward citation graph
- `s2_search_authors` — Author search with h-index and citation counts
- `s2_author_details` — Detailed author profile
- `s2_author_papers` — All papers by an author
- `s2_recommend_papers` — "Papers like this one" recommendations
- `s2_batch_papers` — **Batch lookup: up to 500 papers in one request**

### arXiv
- `arxiv_search` — Search with full arXiv syntax (`au:`, `ti:`, `abs:`, `cat:`)
- `arxiv_paper` — Get paper by arXiv ID or URL
- `arxiv_by_author` — Papers by author, sorted by date

### medRxiv / bioRxiv
- `medrxiv_search` — Keyword search across preprints
- `medrxiv_by_date` — Preprints posted in a date range
- `medrxiv_preprint` — Preprint details with version history
- `medrxiv_publication_status` — Check if a preprint has been journal-published
- `medrxiv_recent_by_category` — Recent preprints by subject area

### OpenAlex
- `openalex_search` — Search 250M+ works, highest throughput available
- `openalex_work` — Work details by OpenAlex ID, DOI, or PMID
- `openalex_search_authors` — Author search with h-index and citation counts
- `openalex_author` — Detailed author profile with research topics
- `openalex_author_works` — Works by a specific author
- `openalex_institution` — Institution details (name, country, works count)

### CrossRef (Web Search Fallback)
- `crossref_search` — High-throughput search (50 req/sec), ideal fallback
- `crossref_doi` — Authoritative DOI metadata lookup
- `crossref_by_author` — Works by author with optional topic filter

### Cache Management
- `cache_stats` — View cache health: entries, size, categories
- `cache_clear` — Clear cache (all or by category)

## When to Use Which Source

| Source | Best for |
|--------|----------|
| **PubMed** (via separate MCP) | Clinical literature, MEDLINE-indexed journals |
| **Semantic Scholar** | AI/ML papers, citation graphs, influence metrics, batch lookups |
| **OpenAlex** | High-volume searches, comprehensive coverage, no rate limit worries |
| **CrossRef** | Fallback when other APIs throttle, DOI verification, citation counts |
| **arXiv** | CS/ML preprints before journal publication |
| **medRxiv/bioRxiv** | Health sciences preprints, tracking publication status |
| **Google Scholar** | Catch-all, books, theses, non-indexed sources |
| **ORCID** | Researcher profiles, collaborator lookup, publication lists |

### Throughput Strategy

When you need to process papers faster than individual APIs allow:

1. **Use OpenAlex first** — 10 req/sec with email, 250M+ works, no auth
2. **S2 batch endpoint** — 500 papers in a single request via `s2_batch_papers`
3. **CrossRef fallback** — 50 req/sec with email, 150M+ works
4. **Cache hit** — Repeated lookups (landmark papers, your own work) are instant
5. **Google Scholar last** — Most aggressive rate limiting, use sparingly

## Local Cache

The server includes a SQLite cache at `~/.cache/academic-research-mcp/cache.db` that:
- Stores paper metadata, search results, and author profiles
- Avoids redundant API calls for frequently accessed papers
- Default TTL: 24 hours for searches, 7 days for paper details
- Override location with `ACADEMIC_CACHE_DIR` env var

## Dependencies

- Python 3.10+
- [scholarly](https://github.com/scholarly-python-package/scholarly) — Google Scholar scraping
- [mcp](https://github.com/modelcontextprotocol/python-sdk) — Model Context Protocol SDK
- [requests](https://docs.python-requests.org/) — HTTP client
- [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML parsing
- [httpx[socks]](https://www.python-httpx.org/) — SOCKS proxy support for scholarly

## License

MIT
