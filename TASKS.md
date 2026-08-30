# TASKS

Durable backlog for academic-research-mcp. Genuinely-deferred work only.

## Active

(none)

## Backlog

- **Consider service-prefixing the generic tool names** (`reviews`, `preprints`, `open_access`, `cache_manage`, e.g. → `ar_reviews` or `literature_reviews`). Flagged by the 2026-08-29 static audit (Medium, low confidence on net benefit): most MCP clients already namespace tools by server (`mcp__academic-research__reviews`), so collisions only matter for clients that flatten names. Renaming is breaking for existing configs/prompts and would need a deprecation note in README + CHANGELOG. Decide deliberately; do not rename casually.

## Done

- 2026-08-29 — Wave 5 performance and review-storage findings remediated: process-shared S2 harvest concurrency and quota pacing, native-async citation caching, concurrent three-provider title resolution with linear DOI-source scoring, accurate post-race snowball counts, and additive review-paper migration with PMID uniqueness, normalized-title backfill/indexing, batch-state deduplication, and one-transaction bulk insertion.
- 2026-08-29 — Earlier 0.2.0 release-prep findings remediated: NCBI api_key leak (sanitized errors across all clients), PubMed token bomb (200-cap + offset pagination), stale release chain (CHANGELOG promoted, versions and `uv.lock` synced, dxt + dist rebuilt), requirements.txt removed in favor of pyproject + CI `pip install -e .`, unique (review_id, doi) dedup index + INSERT OR IGNORE, sticky-active-review startup warning, destructiveHint on delete_review.
