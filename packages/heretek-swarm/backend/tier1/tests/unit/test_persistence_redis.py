"""Unit tests for tier1.persistence.redis.

All aioredis interactions are mocked; no real redis is contacted.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.deliberation.state import initial_state
from tier1.persistence.redis import RedisCache


def _make_client() -> MagicMock:
    client = MagicMock()
    client.ping = AsyncMock(return_value=True)
    client.aclose = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.delete = AsyncMock(return_value=1)
    return client


def test_init_stores_url_ttl_and_none_client() -> None:
    c = RedisCache(url="redis://x:6379", ttl_s=60)
    assert c.url == "redis://x:6379"
    assert c.ttl_s == 60
    assert c.client is None


def test_init_zero_ttl_is_allowed() -> None:
    c = RedisCache(url="u", ttl_s=0)
    assert c.ttl_s == 0


async def test_connect_creates_client_and_pings() -> None:
    fake_client = _make_client()
    with patch("tier1.persistence.redis.aioredis.from_url", return_value=fake_client) as mock_from:
        c = RedisCache(url="redis://x:6379", ttl_s=10)
        await c.connect()

    mock_from.assert_called_once()
    args, kwargs = mock_from.call_args
    assert args[0] == "redis://x:6379"
    assert kwargs.get("decode_responses") is True
    fake_client.ping.assert_awaited_once()
    assert c.client is fake_client


async def test_close_noop_when_client_none() -> None:
    c = RedisCache(url="u", ttl_s=60)
    c.client = None
    await c.close()
    await c.close()
    assert c.client is None


async def test_close_aclose_and_clears() -> None:
    c = RedisCache(url="u", ttl_s=60)
    fake = _make_client()
    c.client = fake
    await c.close()
    fake.aclose.assert_awaited_once()
    assert c.client is None


def test_key_format_includes_id() -> None:
    c = RedisCache(url="u", ttl_s=60)
    assert c._key("abc") == "tier1:state:abc"


def test_key_format_handles_uuid_shaped_id() -> None:
    c = RedisCache(url="u", ttl_s=60)
    out = c._key("12345678-1234-1234-1234-123456789012")
    assert out == "tier1:state:12345678-1234-1234-1234-123456789012"


async def test_put_state_asserts_client_set() -> None:
    c = RedisCache(url="u", ttl_s=60)
    c.client = None
    state = initial_state(deliberation_id="d1", problem="p")
    with pytest.raises(AssertionError):
        await c.put_state(state)


async def test_put_state_serializes_and_sets_with_ttl() -> None:
    c = RedisCache(url="u", ttl_s=123)
    fake = _make_client()
    c.client = fake
    state = initial_state(deliberation_id="d1", problem="p")
    await c.put_state(state)

    fake.set.assert_awaited_once()
    args, kwargs = fake.set.await_args
    assert args[0] == "tier1:state:d1"
    # 2nd positional arg = payload (json string)
    payload = args[1]
    assert isinstance(payload, str)
    assert '"deliberation_id": "d1"' in payload or '"deliberation_id":"d1"' in payload
    # TTL via ex=
    assert kwargs.get("ex") == 123 or (len(args) >= 3 and args[2] == 123)


async def test_get_state_asserts_client_set() -> None:
    c = RedisCache(url="u", ttl_s=60)
    c.client = None
    with pytest.raises(AssertionError):
        await c.get_state("d1")


async def test_get_state_returns_none_when_missing() -> None:
    c = RedisCache(url="u", ttl_s=60)
    fake = _make_client()
    fake.get = AsyncMock(return_value=None)
    c.client = fake
    assert await c.get_state("missing") is None
    fake.get.assert_awaited_once_with("tier1:state:missing")


async def test_get_state_returns_parsed_state() -> None:
    import json as _json

    c = RedisCache(url="u", ttl_s=60)
    fake = _make_client()
    state = initial_state(deliberation_id="d1", problem="p")
    fake.get = AsyncMock(return_value=_json.dumps(state, default=lambda o: o.model_dump()))
    c.client = fake
    out = await c.get_state("d1")
    assert out is not None
    assert out["deliberation_id"] == "d1"
    assert out["problem"] == "p"


async def test_drop_state_asserts_client_set() -> None:
    c = RedisCache(url="u", ttl_s=60)
    c.client = None
    with pytest.raises(AssertionError):
        await c.drop_state("d1")


async def test_drop_state_deletes_key() -> None:
    c = RedisCache(url="u", ttl_s=60)
    fake = _make_client()
    c.client = fake
    await c.drop_state("d1")
    fake.delete.assert_awaited_once_with("tier1:state:d1")
