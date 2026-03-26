"""
Shared HTTP client with connection pooling, retry logic, and timeouts.

All API clients should use get_session() instead of raw requests.get()
to benefit from:
  - Connection pooling (reuse TCP connections across requests)
  - Automatic retry with exponential backoff on 429/5xx
  - Consistent timeouts
  - SSL certificate handling
"""

import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Singleton session
_session = None

DEFAULT_TIMEOUT = 15  # seconds
BATCH_TIMEOUT = 30    # for batch/bulk endpoints


def get_session() -> requests.Session:
    """
    Get or create a shared requests.Session with retry logic and connection pooling.

    Retry strategy:
      - 3 retries on 429 (rate limited), 500, 502, 503, 504
      - Exponential backoff: 1s, 2s, 4s
      - Respects Retry-After header from 429 responses
    """
    global _session
    if _session is None:
        _session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # 1s, 2s, 4s
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
        _session.mount("http://", adapter)

    return _session


def get(url: str, timeout: int = DEFAULT_TIMEOUT, **kwargs) -> requests.Response:
    """
    Make a GET request with connection pooling and retry logic.

    Parameters:
        url: Request URL.
        timeout: Request timeout in seconds.
        **kwargs: Additional arguments passed to session.get().

    Returns:
        requests.Response object.
    """
    session = get_session()
    return session.get(url, timeout=timeout, **kwargs)


def post(url: str, timeout: int = BATCH_TIMEOUT, **kwargs) -> requests.Response:
    """
    Make a POST request with connection pooling and retry logic.

    Parameters:
        url: Request URL.
        timeout: Request timeout in seconds.
        **kwargs: Additional arguments passed to session.post().

    Returns:
        requests.Response object.
    """
    session = get_session()
    return session.post(url, timeout=timeout, **kwargs)


def get_env(name: str, default: str = "") -> str:
    """
    Get an environment variable at call time (not import time).
    This ensures env vars set by Claude Desktop's config are picked up.

    Parameters:
        name: Environment variable name.
        default: Default value if not set.

    Returns:
        The environment variable value.
    """
    return os.environ.get(name, default)
