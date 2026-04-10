"""
Shared test fixtures and data for academic-research-mcp tests.
"""

import sys
import os
import pytest

# Ensure the project root is on the path so imports work from any cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Sample paper data (reused across test modules)
# ---------------------------------------------------------------------------

SAMPLE_PAPER = {
    "id": "W2741809807",
    "doi": "10.1038/nature12373",
    "title": "An integrated encyclopedia of DNA elements in the human genome",
    "year": 2012,
    "cited_by_count": 5000,
    "authors": [{"name": "ENCODE Project Consortium"}],
    "abstract": "The human genome encodes the blueprint of life.",
    "source": "Nature",
}

SAMPLE_PAPER_NO_DOI = {
    "id": "W1234567890",
    "doi": None,
    "title": "A paper without a DOI",
    "year": 2020,
    "cited_by_count": 10,
    "authors": [{"name": "Jane Doe"}],
    "abstract": "This paper has no DOI.",
    "source": "Preprint Server",
}

SAMPLE_PAPER_DUPLICATE = {
    "id": "W2741809807",  # same id as SAMPLE_PAPER
    "doi": "10.1038/nature12373",
    "title": "An integrated encyclopedia of DNA elements in the human genome",
    "year": 2012,
    "cited_by_count": 5001,  # slightly different count
    "authors": [{"name": "ENCODE Project Consortium"}],
    "abstract": "Duplicate entry.",
    "source": "Nature",
}


# ---------------------------------------------------------------------------
# DB fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db_dir(tmp_path, monkeypatch):
    """
    Fixture that:
    1. Points ACADEMIC_CACHE_DIR at a temp directory.
    2. Resets the db._conn singleton so each test gets a fresh connection.
    3. Cleans up after the test.
    """
    import db

    monkeypatch.setenv("ACADEMIC_CACHE_DIR", str(tmp_path))

    # Reset singleton before the test
    db._conn = None

    yield tmp_path

    # Teardown: close and reset singleton
    if db._conn is not None:
        try:
            db._conn.close()
        except Exception:
            pass
        db._conn = None
