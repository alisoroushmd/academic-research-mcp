# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] - 2026-08-29

### Added

- **`delete_review` now advertises `destructiveHint`** via MCP `ToolAnnotations`, so clients can warn before an irreversible deletion. (`server.py`, `tests/test_server_tools.py`)

- **DB-level dedup backstop for review papers.** A unique `(review_id, LOWER(doi))` index plus `INSERT OR IGNORE` closes the cross-process window the Python-side duplicate check cannot see (two server processes sharing one database). Legacy databases that already contain duplicate DOIs degrade gracefully: index creation is skipped with a warning and dedup falls back to the Python check alone. (`review_manager.py`, `tests/test_review_manager.py`)

- **Startup warning for a sticky active review.** The active review persists in SQLite across restarts, so a review activated weeks ago silently keeps auto-logging every search. The server now warns at startup with the review name and age, and points to `set_active_review(null)`. (`server.py`, `review_manager.py`, `tests/test_review_manager.py`)

- **`MANIFEST.in` prunes `venv/`, `build/`, `dist/`, `docs/`, and cache dirs from source distributions.** Prevents a multi-hundred-MB sdist if `venv/` is present in the working directory at build time. (`MANIFEST.in`)

- **`CROSSREF_EMAIL` is now configurable in the DXT manifest.** Users who want a different CrossRef identity from their OpenAlex email can set it via the Claude Desktop UI; the existing fallback to `OPENALEX_EMAIL` still applies when left blank. (`dxt/manifest.json`)

### Changed

- **PubMed searches are paginated and capped at 200 results per call.** `search_papers(source="pubmed")` previously accepted `num_results` up to 10,000 and EFetch'ed the entire result set — in 200-record batches — into a single tool response. It now caps at 200 like every other source; PubMed responses return `{papers, total_count, offset, returned, has_more}` and larger result sets are paged with the new `offset` argument (E-utilities `retstart`). (`pubmed_client.py`, `server.py`, `tests/test_pubmed_client.py`, `tests/test_server_tools.py`)

- **`pyproject.toml` is the single source of dependencies.** `requirements.txt` is removed — it still pinned `mcp>=1.0`, contradicting `pyproject.toml`, and CI installed from it. CI now installs the project itself (`pip install -e .`), `uv.lock` records the release environment, and `pip-audit` audits the resolved environment. (`requirements.txt`, `uv.lock`, `.github/workflows/ci.yml`)

- **`mcp` dependency lower bound tightened to `>=1.8`.** `FastMCP` (the decorator API used throughout `server.py`) was not available in 1.0.x, and `ToolAnnotations` on tool registration requires ≥1.8; the tighter bound prevents a confusing error at install time. (`pyproject.toml`)

- **README Dependencies section now lists all six runtime packages.** Previously omitted `defusedxml` (safe XML parsing for PubMed/arXiv responses) and `pip-system-certs` (OS certificate store for corporate/VPN installs). (`README.md`)

- **DXT manifest email fields are no longer marked `sensitive`.** `openalex_email` and `crossref_email` now display as plain text in the Claude Desktop UI. An email is contact information for the OpenAlex/CrossRef polite pool, not a secret, and masking it made it harder for users to verify the identity they registered. (API keys remain `sensitive`.) (`dxt/manifest.json`, `dxt/academic-research-mcp.dxt`)

### Fixed

- **`open_access` failure modes are now self-diagnosing.** Previously a missing/placeholder `OPENALEX_EMAIL`, an empty/invalid DOI, and a DOI genuinely absent from Unpaywall all collapsed into an indistinguishable `is_oa=False` / empty `pdf_url` (especially in batch mode, where `batch_check_oa` silently discarded the underlying `error`). This made a config problem look like a global "nothing is open access" outage. Each result now carries an `error_type` (`config` / `invalid_doi` / `not_in_unpaywall` / `api_error`), config problems also set `config_issue: True`, and placeholder emails (`example.com`, `your-email`, `changeme`, …) plus malformed addresses and Unpaywall `422` responses are detected and reported with an actionable message. (`unpaywall_client.py`, `tests/test_unpaywall_client.py`)

- **CrossRef year filter now handles `>2021` / `<2020` prefix syntax.** Previously silently emitted a malformed filter value and returned no results; ISO-date strings like `"2020-01-01"` now also fail gracefully instead of producing a wrong query. (`crossref_client.py`)

- **ORCID author search now fetches minimal profiles in parallel.** Was making N sequential HTTP calls (up to 5 × 10s timeouts = 50s hang); now uses a `ThreadPoolExecutor(max_workers=5)`. (`orcid_client.py`)

- **`test_prisma_counts.py` fixture no longer sets a non-existent module attribute.** `review_manager._active_review_id` does not exist — active-review state is in the DB, which is already reset per-test by `tmp_db_dir`. The spurious assignment is removed. (`tests/test_prisma_counts.py`)

- **`get_paper_network(direction="both")` return type corrected to `Union[List, Dict]`.** Was declared `List[Dict]` but returned a plain `dict`, breaking any client iterating over the result as a list. Also added `return_exceptions=True` so a partial S2 failure returns the successful direction rather than raising. (`server.py`)

- **`openalex_client.get_author` and `get_author_works` are now cached.** Was the only pair of single-entity OpenAlex lookups without `@cache.cached`; frequently called in systematic-review workflows. (`openalex_client.py`)

- **All API clients now send a descriptive `User-Agent` header.** Set once in `http_client.get_session()` (sync) and `get_async_client()` (async) — applies to all 9 source clients without per-client changes. (`http_client.py`)

- **`cache.py` `_tables_created` guard is now correctly double-checked inside the lock.** Previously set after releasing the lock, allowing two threads to both enter the DDL block; now set inside the `with _lock:` block before commit. (`cache.py`)

### Security

- **NCBI `api_key` no longer leaks through HTTP error messages.** Status and transport exceptions can embed the full request URL — including the `api_key` query parameter PubMed requires in the URL — and `server.py` returns `str(e)` to the MCP client and logs it. API clients now raise HTTP-status failures through `http_client.raise_for_status_sanitized()`, while the shared `get()` / `post()` boundary also sanitizes connection and timeout failures. Both paths redact query strings (API keys and polite-pool emails) and report only the exception/status plus endpoint path. (`http_client.py`, `pubmed_client.py`, `arxiv_client.py`, `crossref_client.py`, `medrxiv_client.py`, `openalex_client.py`, `orcid_client.py`, `semantic_scholar_client.py`, `tests/test_http_client.py`, `tests/test_pubmed_client.py`)
