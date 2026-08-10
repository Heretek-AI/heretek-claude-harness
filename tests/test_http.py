"""Tests for scripts/_http.py — shared HTTP response guards."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts._http import MAX_RESPONSE_BYTES, check_content_length


def _mock_response(content_length: str | None) -> MagicMock:
    """Build a requests-Response-shaped mock with the given Content-Length header."""
    headers: dict[str, str] = {}
    if content_length is not None:
        headers["Content-Length"] = content_length
    r = MagicMock()
    r.headers = headers
    return r


@pytest.mark.parametrize(
    ("content_length", "should_raise"),
    [
        ("99999999999", True),  # ~100 GB → reject
        ("abc", False),  # malformed → silently allow
        ("1024", False),  # small OK response → silently allow
        (None, False),  # missing header (chunked) → silently allow
        (str(MAX_RESPONSE_BYTES), False),  # exactly at cap → silently allow
        (str(MAX_RESPONSE_BYTES + 1), True),  # one byte over → reject
    ],
    ids=[
        "huge_content_length",
        "malformed_non_integer",
        "small_response",
        "missing_header",
        "exactly_at_cap",
        "one_over_cap",
    ],
)
def test_check_content_length(content_length: str | None, should_raise: bool) -> None:
    response = _mock_response(content_length)
    if should_raise:
        with pytest.raises(ValueError, match="exceeds cap"):
            check_content_length(response)
    else:
        # Must not raise — silently passes through.
        check_content_length(response)
