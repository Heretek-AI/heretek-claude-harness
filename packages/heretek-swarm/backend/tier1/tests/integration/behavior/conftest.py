"""vcrpy configuration for behavior tests.

Patches the openai SDK's HTTP transport. Cassettes are committed to the
repo (scrubbed of auth headers) so PR CI replays them without secrets.

Refresh a cassette:
    rm tests/integration/behavior/cassettes/test_foo.yaml
    RECORD_MINIMAX=1 TIER1_MINIMAX_API_KEY=<key> pytest tests/integration/behavior/test_foo.py
"""

from __future__ import annotations

from pathlib import Path

import pytest
import vcr


# vcrpy cassettes are matched on method + URI. We filter Authorization
# so matches work even when the cassette is replayed in an environment
# with a different (or no) live key.
_AUTH_HEADER_FILTER = ("authorization",)
_OPENAI_BETA_HEADER_FILTER = ("x-stainless-raw-response", "x-stainless-raw-request")


def _scrub_request(request: vcr.request.Request) -> vcr.request.Request:
    """Replace live Authorization header values with REDACTED on record.

    Runs only when recording. On replay, vcrpy injects the recorded value
    verbatim — this scrubber doesn't fire.
    """
    auth = request.headers.get("authorization")
    if auth:
        request.headers["authorization"] = "Bearer REDACTED"
    return request


@pytest.fixture()
def vcr_cassette(
    cassette_dir: Path, record_mode: str, request: pytest.FixtureRequest
) -> vcr.use_cassette:
    """A `vcr.use_cassette` context manager bound to the test's cassette file."""
    cassette_name = f"{request.node.name}.yaml"
    cassette_path = cassette_dir / cassette_name
    return vcr.use_cassette(
        str(cassette_path),
        record_mode=record_mode,
        filter_headers=_AUTH_HEADER_FILTER + _OPENAI_BETA_HEADER_FILTER,
        before_record_request=_scrub_request,
        match_on=["method", "scheme", "host", "port", "path", "query"],
    )
