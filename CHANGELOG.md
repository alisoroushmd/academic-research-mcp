# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **`MANIFEST.in` prunes `venv/`, `build/`, `dist/`, `docs/`, and cache dirs from source distributions.** Prevents a multi-hundred-MB sdist if `venv/` is present in the working directory at build time. (`MANIFEST.in`)

- **`CROSSREF_EMAIL` is now configurable in the DXT manifest.** Users who want a different CrossRef identity from their OpenAlex email can set it via the Claude Desktop UI; the existing fallback to `OPENALEX_EMAIL` still applies when left blank. (`dxt/manifest.json`)

### Changed

- **`mcp` dependency lower bound tightened to `>=1.2`.** `FastMCP` (the decorator API used throughout `server.py`) was not available in 1.0.x; the tighter bound prevents a confusing import error at install time. (`pyproject.toml`)

- **README Dependencies section now lists all six runtime packages.** Previously omitted `defusedxml` (safe XML parsing for PubMed/arXiv responses) and `pip-system-certs` (OS certificate store for corporate/VPN installs). (`README.md`)

### Fixed

- **`openalex_email` now stored as a sensitive field in the DXT manifest.** Previously displayed as plain text in the Claude Desktop UI. (`dxt/manifest.json`)

- **CrossRef year filter now handles `>2021` / `<2020` prefix syntax.** Previously silently emitted a malformed filter value and returned no results; ISO-date strings like `"2020-01-01"` now also fail gracefully instead of producing a wrong query. (`crossref_client.py`)

- **ORCID author search now fetches minimal profiles in parallel.** Was making N sequential HTTP calls (up to 5 × 10s timeouts = 50s hang); now uses a `ThreadPoolExecutor(max_workers=5)`. (`orcid_client.py`)

- **`test_prisma_counts.py` fixture no longer sets a non-existent module attribute.** `review_manager._active_review_id` does not exist — active-review state is in the DB, which is already reset per-test by `tmp_db_dir`. The spurious assignment is removed. (`tests/test_prisma_counts.py`)

- **`get_paper_network(direction="both")` return type corrected to `Union[List, Dict]`.** Was declared `List[Dict]` but returned a plain `dict`, breaking any client iterating over the result as a list. Also added `return_exceptions=True` so a partial S2 failure returns the successful direction rather than raising. (`server.py`)

- **`openalex_client.get_author` and `get_author_works` are now cached.** Was the only pair of single-entity OpenAlex lookups without `@cache.cached`; frequently called in systematic-review workflows. (`openalex_client.py`)

- **All API clients now send a descriptive `User-Agent` header.** Set once in `http_client.get_session()` (sync) and `get_async_client()` (async) — applies to all 9 source clients without per-client changes. (`http_client.py`)

- **`cache.py` `_tables_created` guard is now correctly double-checked inside the lock.** Previously set after releasing the lock, allowing two threads to both enter the DDL block; now set inside the `with _lock:` block before commit. (`cache.py`)
