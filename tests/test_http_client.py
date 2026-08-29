"""Regression tests for credential-safe shared HTTP failures."""

from unittest.mock import MagicMock, patch

import pytest
import requests

import http_client


@pytest.mark.parametrize("method", ["get", "post"])
def test_transport_failure_redacts_prepared_query_string(method):
    secret = "ncbi-secret-value"
    prepared = requests.Request(
        method.upper(),
        "https://example.test/endpoint",
        params={"api_key": secret, "email": "person@example.test"},
    ).prepare()
    original = requests.ConnectionError(
        f"failed for {prepared.url}", request=prepared
    )
    session = MagicMock()
    getattr(session, method).side_effect = original

    with patch("http_client.get_session", return_value=session):
        with pytest.raises(requests.ConnectionError) as exc_info:
            getattr(http_client, method)(
                "https://example.test/endpoint",
                params={"api_key": secret},
            )

    message = str(exc_info.value)
    assert secret not in message
    assert "person@example.test" not in message
    assert message == (
        "ConnectionError for https://example.test/endpoint "
        "(query string redacted)"
    )
    assert exc_info.value.request is None
