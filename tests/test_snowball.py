"""
Tests for orchestrator.harvest_citations (snowball harvesting logic).

Review-level deduplication is tested in test_review_manager.py.
"""

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_citation(i, doi_prefix="10.9999/cite"):
    return {
        "title": f"Citing paper {i}",
        "authors": [f"Citer {i}"],
        "year": 2024,
        "doi": f"{doi_prefix}.{i}",
        "pmid": None,
        "citationCount": 5,
    }


def _make_reference(i, doi_prefix="10.9999/ref"):
    return {
        "title": f"Referenced paper {i}",
        "authors": [f"Author {i}"],
        "year": 2020,
        "doi": f"{doi_prefix}.{i}",
        "pmid": None,
        "citationCount": 20,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_module_state(tmp_db_dir):
    """Reset db singleton before each test."""
    import db

    db._conn = None
    yield
    if db._conn is not None:
        try:
            db._conn.close()
        except Exception:
            pass
        db._conn = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("semantic_scholar_client.get_paper_citations")
@patch("semantic_scholar_client.get_paper_references")
def test_harvest_both_directions(mock_refs, mock_cites, tmp_db_dir):
    """Both directions: 5 citations + 3 references = 8 total, all unique."""
    from orchestrator import harvest_citations

    mock_cites.return_value = [_make_citation(i) for i in range(5)]
    mock_refs.return_value = [_make_reference(i) for i in range(3)]

    result = harvest_citations(
        seed_paper_ids=["seed_id_1"],
        direction="both",
    )

    assert result["total_harvested"] == 8
    assert len(result["candidates"]) == 8
    assert result["duplicates_within_snowball"] == 0
    assert result["seed_count"] == 1


@patch("semantic_scholar_client.get_paper_citations")
@patch("semantic_scholar_client.get_paper_references")
def test_harvest_deduplicates_across_seeds(mock_refs, mock_cites, tmp_db_dir):
    """Two seeds share one citation — duplicates_within_snowball should be 1."""
    from orchestrator import harvest_citations

    shared = _make_citation(99, doi_prefix="10.9999/shared")
    seed1_citations = [shared, _make_citation(1), _make_citation(2)]
    seed2_citations = [shared, _make_citation(3)]

    mock_refs.return_value = []
    mock_cites.side_effect = [seed1_citations, seed2_citations]

    result = harvest_citations(
        seed_paper_ids=["seed_id_1", "seed_id_2"],
        direction="forward",
    )

    # 3 from seed1 + 2 from seed2 = 5 total harvested
    assert result["total_harvested"] == 5
    # After dedup within snowball: 4 unique (shared counted once)
    assert result["duplicates_within_snowball"] == 1
    assert len(result["candidates"]) == 4


@patch("semantic_scholar_client.get_paper_citations")
@patch("semantic_scholar_client.get_paper_references")
def test_harvest_deduplicates_against_review_at_server_level(
    mock_refs, mock_cites, tmp_db_dir
):
    """Verify harvest returns candidates that can be deduped against review."""
    import review_manager
    from orchestrator import harvest_citations

    review_manager._tables_initialized = False

    pre_existing = _make_citation(0, doi_prefix="10.9999/existing")

    review = review_manager.create_review("Snowball Test 3")
    search_id = review_manager.log_search(
        review["id"], "openalex", "prior search", {}, 1, 1
    )
    review_manager.add_papers(review["id"], search_id, [pre_existing], "openalex")

    # Snowball will return only that pre-existing paper
    mock_cites.return_value = [pre_existing]
    mock_refs.return_value = []

    result = harvest_citations(
        seed_paper_ids=["seed_id_1"],
        direction="both",
    )

    assert result["total_harvested"] == 1
    assert len(result["candidates"]) == 1

    # Server-level dedup: verify the candidate IS a duplicate against the review
    assert review_manager.is_duplicate(review["id"], result["candidates"][0])


def test_async_harvest_keyed_requests_are_capped_at_ten(monkeypatch):
    """Authenticated S2 harvests use native async I/O with max concurrency 10."""
    import orchestrator

    active = 0
    max_active = 0

    async def fake_fetch(seed_id, num_results):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1
        return [_make_citation(int(seed_id))]

    def sync_must_not_run(*args, **kwargs):
        raise AssertionError("native async S2 client should be used")

    monkeypatch.setenv("S2_API_KEY", "test-key")
    monkeypatch.setenv("S2_API_KEY_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setattr(orchestrator.s2, "async_get_paper_citations", fake_fetch)
    monkeypatch.setattr(orchestrator.s2, "get_paper_citations", sync_must_not_run)

    result = asyncio.run(
        orchestrator.async_harvest_citations(
            [str(i) for i in range(25)], direction="forward"
        )
    )

    assert max_active == 10
    assert result["total_harvested"] == 25


def test_concurrent_harvests_share_the_keyed_provider_limiter(monkeypatch):
    """Two harvest calls cannot each consume a separate ten-request budget."""
    import orchestrator

    active = 0
    max_active = 0

    async def fake_fetch(seed_id, num_results):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0)
        active -= 1
        return [_make_citation(int(seed_id))]

    monkeypatch.setenv("S2_API_KEY", "test-key")
    monkeypatch.setenv("S2_API_KEY_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setattr(orchestrator.s2, "async_get_paper_citations", fake_fetch)

    async def run_both():
        return await asyncio.gather(
            orchestrator.async_harvest_citations(
                [str(i) for i in range(12)], direction="forward"
            ),
            orchestrator.async_harvest_citations(
                [str(i) for i in range(12, 24)], direction="forward"
            ),
        )

    first, second = asyncio.run(run_both())

    assert max_active == 10
    assert first["total_harvested"] == 12
    assert second["total_harvested"] == 12


def test_async_harvest_anonymous_requests_are_serial_and_paced(monkeypatch):
    """Anonymous S2 calls permit one in flight and pause one second per call."""
    import orchestrator

    active = 0
    max_active = 0
    sleeps = []
    real_sleep = asyncio.sleep

    async def fake_fetch(seed_id, num_results):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await real_sleep(0)
        active -= 1
        return [_make_citation(int(seed_id))]

    async def fake_sleep(delay):
        sleeps.append(delay)
        await real_sleep(0)

    monkeypatch.delenv("S2_API_KEY", raising=False)
    monkeypatch.setattr(orchestrator.s2, "async_get_paper_citations", fake_fetch)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    result = asyncio.run(
        orchestrator.async_harvest_citations(["1", "2", "3"], direction="forward")
    )

    assert max_active == 1
    assert len(sleeps) == 2
    assert all(0 < delay <= 1.0 for delay in sleeps)
    assert result["total_harvested"] == 3


def test_sync_and_async_related_calls_share_canonical_cache_key(
    monkeypatch, tmp_db_dir
):
    import cache
    import semantic_scholar_client as s2

    cache._tables_created = False
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"data": []}
    monkeypatch.setattr(s2.http_client, "get", lambda *a, **k: response)

    assert s2.get_paper_citations("seed", num_results=100) == []

    async def network_must_not_run(*args, **kwargs):
        raise AssertionError("async call should reuse the sync cache entry")

    monkeypatch.setattr(s2.http_client, "async_get", network_must_not_run)
    assert asyncio.run(s2.async_get_paper_citations("seed", 100)) == []


def test_many_cached_harvest_edges_bypass_limiter_and_provider(monkeypatch, tmp_db_dir):
    import cache
    import orchestrator

    cache._tables_created = False
    seeds = [str(i) for i in range(25)]
    for seed_id in seeds:
        cache.put(
            orchestrator.s2._related_cache_key("citations", seed_id, 100),
            [_make_citation(int(seed_id))],
            category="citations",
            ttl=cache.SEARCH_TTL,
        )

    limiter_calls = 0
    provider_calls = 0

    class CountingLimiter:
        async def run(self, awaitable_factory):
            nonlocal limiter_calls
            limiter_calls += 1
            return await awaitable_factory()

    async def counting_provider(seed_id, num_results):
        nonlocal provider_calls
        provider_calls += 1
        return []

    monkeypatch.delenv("S2_API_KEY", raising=False)
    monkeypatch.setattr(
        orchestrator, "_get_s2_harvest_limiter", lambda has_key: CountingLimiter()
    )
    monkeypatch.setattr(orchestrator.s2, "async_get_paper_citations", counting_provider)

    result = asyncio.run(
        orchestrator.async_harvest_citations(seeds, direction="forward")
    )

    assert limiter_calls == 0
    assert provider_calls == 0
    assert result["total_harvested"] == 25


def test_identical_concurrent_edges_use_one_flight_and_no_duplicate_pacing(
    monkeypatch, tmp_db_dir
):
    import asyncio as asyncio_module

    import cache
    import orchestrator

    cache._tables_created = False
    provider_calls = 0
    pacing_sleeps = []
    real_sleep = asyncio_module.sleep

    async def fake_provider(seed_id, num_results):
        nonlocal provider_calls
        provider_calls += 1
        await real_sleep(0)
        return [_make_citation(1)]

    async def counting_sleep(delay):
        pacing_sleeps.append(delay)
        await real_sleep(0)

    monkeypatch.delenv("S2_API_KEY", raising=False)
    monkeypatch.setattr(orchestrator.s2, "async_get_paper_citations", fake_provider)
    monkeypatch.setattr(asyncio_module, "sleep", counting_sleep)

    result = asyncio.run(
        orchestrator.async_harvest_citations(["same-seed"] * 5, direction="forward")
    )

    assert provider_calls == 1
    assert pacing_sleeps == []
    assert result["total_harvested"] == 5
