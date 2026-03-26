# Academic Research MCP Server

A unified [Model Context Protocol](https://modelcontextprotocol.io/) server that provides AI assistants with access to five academic research APIs through **23 tools**. Designed for biomedical researchers who work across clinical medicine and computer science.

## APIs & Tools

| API | Tools | Auth | What it does |
|-----|-------|------|-------------|
| **Google Scholar** | 3 | None | Keyword search, advanced search (author + year filters), author profiles |
| **ORCID** | 4 | None | Researcher search, full profiles, publication lists, funding history |
| **Semantic Scholar** | 8 | Optional | Paper search, citation graphs, author metrics, paper recommendations |
| **arXiv** | 3 | None | CS/ML preprint search with arXiv query syntax, paper lookup, author papers |
| **medRxiv/bioRxiv** | 5 | None | Preprint search, date-range browsing, publication status tracking |

No API keys required. Optionally set `S2_API_KEY` for higher Semantic Scholar rate limits.

## Quick Start

```bash
git clone https://github.com/asoroush/academic-research-mcp.git
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
      "args": ["/path/to/academic-research-mcp/server.py"]
    }
  }
}
```

For higher Semantic Scholar rate limits, add an API key (free from [semanticscholar.org/product/api](https://www.semanticscholar.org/product/api)):

```json
{
  "mcpServers": {
    "academic-research": {
      "command": "/path/to/academic-research-mcp/venv/bin/python",
      "args": ["/path/to/academic-research-mcp/server.py"],
      "env": {
        "S2_API_KEY": "your-key-here"
      }
    }
  }
}
```

Restart Claude Desktop after saving.

## All 23 Tools

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

## When to Use Which Source

| Source | Best for |
|--------|----------|
| **PubMed** | Clinical literature, MEDLINE-indexed journals |
| **Semantic Scholar** | AI/ML papers, citation graphs, influence metrics |
| **arXiv** | CS/ML preprints before journal publication |
| **medRxiv/bioRxiv** | Health sciences preprints, tracking publication status |
| **Google Scholar** | Catch-all fallback, books, theses, non-indexed sources |
| **ORCID** | Researcher profiles, collaborator lookup, publication lists |

## Dependencies

- Python 3.10+
- [scholarly](https://github.com/scholarly-python-package/scholarly) — Google Scholar scraping
- [mcp](https://github.com/modelcontextprotocol/python-sdk) — Model Context Protocol SDK
- [requests](https://docs.python-requests.org/) — HTTP client
- [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML parsing
- [httpx[socks]](https://www.python-httpx.org/) — SOCKS proxy support for scholarly

## Rate Limits

| API | Free Tier | With Key |
|-----|-----------|----------|
| Google Scholar | ~100 requests before CAPTCHA | Use proxy via scholarly |
| ORCID | Unlimited (public API) | N/A |
| Semantic Scholar | 100 req / 5 min | 1 req / sec |
| arXiv | 1 req / 3 sec (enforced) | N/A |
| medRxiv/bioRxiv | Reasonable use | N/A |

## License

MIT
