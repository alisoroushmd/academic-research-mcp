"""
Shared HTTP clients with connection pooling, retry logic, and timeouts.

Provides both sync (requests) and async (httpx) clients. API clients should
use the async client for true concurrency; the sync client remains available
for contexts that require blocking calls (e.g., cache decorator internals).
"""

import os

import httpx
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --------------------------------------------------------------------------
# Sync client (requests) — used by cache decorator, scholarly, etc.
# --------------------------------------------------------------------------

_session = None

DEFAULT_TIMEOUT = 15  # seconds
BATCH_TIMEOUT = 30  # for batch/bulk endpoints


def get_session() -> requests.Session:
    """
    Get or create a shared requests.Session with retry logic and connection pooling.
    """
    global _session
    if _session is None:
        _session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            respect_retry_after_header=True,
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20,
        )
        _session.mount("https://", adapter)

    return _session


def _require_https(url: str) -> None:
    """Reject plain HTTP URLs to prevent accidental credential leakage."""
    if url.startswith("http://"):
        raise ValueError(
            f"HTTP (non-TLS) requests are blocked for security. Use HTTPS: {url}"
        )


def get(url: str, timeout: int = DEFAULT_TIMEOUT, **kwargs) -> requests.Response:
    """Make a GET request with connection pooling and retry logic."""
    _require_https(url)
    session = get_session()
    return session.get(url, timeout=timeout, **kwargs)


def post(url: str, timeout: int = BATCH_TIMEOUT, **kwargs) -> requests.Response:
    """Make a POST request with connection pooling and retry logic."""
    _require_https(url)
    session = get_session()
    return session.post(url, timeout=timeout, **kwargs)


# --------------------------------------------------------------------------
# Async client (httpx) — preferred for MCP tool handlers
# --------------------------------------------------------------------------

_async_client = None

# httpx transport with retry-like behavior
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3


def _get_async_transport() -> httpx.AsyncHTTPTransport:
    return httpx.AsyncHTTPTransport(
        retries=_MAX_RETRIES,
        http2=False,
    )


def get_async_client() -> httpx.AsyncClient:
    """
    Get or create a shared httpx.AsyncClient with connection pooling.

    httpx's built-in transport retries handle connection-level retries.
    For HTTP-level retries (429, 5xx), use async_get/async_post which
    implement retry with backoff.
    """
    global _async_client
    if _async_client is None:
        _async_client = httpx.AsyncClient(
            transport=_get_async_transport(),
            timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=10.0),
            follow_redirects=True,
        )
    return _async_client


async def async_get(
    url: str, timeout: float = DEFAULT_TIMEOUT, **kwargs
) -> httpx.Response:
    """Async GET with retry on 429/5xx and exponential backoff."""
    import asyncio

    _require_https(url)
    client = get_async_client()
    for attempt in range(_MAX_RETRIES + 1):
        resp = await client.get(url, timeout=timeout, **kwargs)
        if resp.status_code not in _RETRY_STATUS_CODES or attempt == _MAX_RETRIES:
            return resp
        # Backoff: 1s, 2s, 4s
        wait = 2**attempt
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = max(wait, int(retry_after))
        await asyncio.sleep(wait)
    return resp


async def async_post(
    url: str, timeout: float = BATCH_TIMEOUT, **kwargs
) -> httpx.Response:
    """Async POST with retry on 429/5xx and exponential backoff."""
    import asyncio

    _require_https(url)
    client = get_async_client()
    for attempt in range(_MAX_RETRIES + 1):
        resp = await client.post(url, timeout=timeout, **kwargs)
        if resp.status_code not in _RETRY_STATUS_CODES or attempt == _MAX_RETRIES:
            return resp
        wait = 2**attempt
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = max(wait, int(retry_after))
        await asyncio.sleep(wait)
    return resp


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def get_env(name: str, default: str = "") -> str:
    """
    Get an environment variable at call time (not import time).
    This ensures env vars set by Claude Desktop's config are picked up.
    """
    return os.environ.get(name, default)
