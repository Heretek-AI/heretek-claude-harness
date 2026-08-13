"""Integration tests for RedisCache. Requires a live Redis at $TIER1_TEST_REDIS_URL."""

from __future__ import annotations

import os

import pytest

from tier1.deliberation.state import initial_state, new_deliberation_id
from tier1.persistence.redis import RedisCache


URL = os.environ.get("TIER1_TEST_REDIS_URL", "")


@pytest.fixture
async def cache():
    if not URL:
        pytest.skip("set TIER1_TEST_REDIS_URL to enable Redis integration tests")
    c = RedisCache(URL, ttl_s=60)
    await c.connect()
    yield c
    await c.drop_state("__test__")
    await c.close()


async def test_put_and_get(cache: RedisCache):
    state = initial_state(deliberation_id="abc", problem="hello")
    await cache.put_state(state)
    got = await cache.get_state("abc")
    assert got is not None
    assert got["problem"] == "hello"


async def test_drop(cache: RedisCache):
    state = initial_state(deliberation_id="abc", problem="hello")
    await cache.put_state(state)
    await cache.drop_state("abc")
    assert await cache.get_state("abc") is None


async def test_ttl_expires():
    pytest.skip("requires TTL manipulation; covered by manual run")
