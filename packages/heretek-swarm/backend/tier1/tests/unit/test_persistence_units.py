"""Unit tests for persistence + memory store modules — Task 6 coverage lift.

Targets low-coverage modules:
- tier1/memory/mem0_store.py
- tier1/memory/nats_memory.py
- tier1/memory/redis_cache.py
- tier1/persistence/redis.py
- tier1/persistence/postgres.py (helpers + close path)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------- mem0_store ----------


async def test_mem0_disabled_returns_none_on_add():
    from tier1.memory.mem0_store import Mem0Backend

    backend = Mem0Backend(api_key=None)
    result = await backend.add("hello", "u1")
    assert result is None


async def test_mem0_disabled_returns_empty_on_search():
    from tier1.memory.mem0_store import Mem0Backend

    backend = Mem0Backend(api_key=None)
    result = await backend.search("q", "u1")
    assert result == []


async def test_mem0_disabled_returns_false_on_update_delete():
    from tier1.memory.mem0_store import Mem0Backend

    backend = Mem0Backend(api_key=None)
    assert await backend.update("id", "text") is False
    assert await backend.delete("id") is False


async def test_mem0_enabled_add_returns_id():
    from tier1.memory.mem0_store import Mem0Backend

    backend = Mem0Backend(api_key="sk-test")
    fake_client = MagicMock()
    fake_client.add = MagicMock(return_value={"id": "mem-1"})
    backend._client = fake_client
    backend._enabled = True
    out = await backend.add("text", "u1", {"k": "v"})
    assert out == "mem-1"
    fake_client.add.assert_called_once()


async def test_mem0_enabled_search_returns_results():
    from tier1.memory.mem0_store import Mem0Backend

    backend = Mem0Backend(api_key="sk-test")
    fake_client = MagicMock()
    fake_client.search = MagicMock(return_value={"results": [{"id": "m1"}]})
    backend._client = fake_client
    backend._enabled = True
    out = await backend.search("q", "u1", top_k=3)
    assert out == [{"id": "m1"}]


async def test_mem0_enabled_search_handles_exception():
    from tier1.memory.mem0_store import Mem0Backend

    backend = Mem0Backend(api_key="sk-test")
    fake_client = MagicMock()
    fake_client.search = MagicMock(side_effect=RuntimeError("boom"))
    backend._client = fake_client
    backend._enabled = True
    out = await backend.search("q", "u1")
    assert out == []


async def test_mem0_enabled_update_success():
    from tier1.memory.mem0_store import Mem0Backend

    backend = Mem0Backend(api_key="sk-test")
    fake_client = MagicMock()
    fake_client.update = MagicMock(return_value=None)
    backend._client = fake_client
    backend._enabled = True
    assert await backend.update("mem-1", "new text") is True


async def test_mem0_enabled_update_exception():
    from tier1.memory.mem0_store import Mem0Backend

    backend = Mem0Backend(api_key="sk-test")
    fake_client = MagicMock()
    fake_client.update = MagicMock(side_effect=RuntimeError("x"))
    backend._client = fake_client
    backend._enabled = True
    assert await backend.update("mem-1", "text") is False


async def test_mem0_enabled_delete_success():
    from tier1.memory.mem0_store import Mem0Backend

    backend = Mem0Backend(api_key="sk-test")
    fake_client = MagicMock()
    fake_client.delete = MagicMock(return_value=None)
    backend._client = fake_client
    backend._enabled = True
    assert await backend.delete("mem-1") is True


async def test_mem0_enabled_delete_exception():
    from tier1.memory.mem0_store import Mem0Backend

    backend = Mem0Backend(api_key="sk-test")
    fake_client = MagicMock()
    fake_client.delete = MagicMock(side_effect=RuntimeError("x"))
    backend._client = fake_client
    backend._enabled = True
    assert await backend.delete("mem-1") is False


async def test_mem0_add_handles_exception():
    from tier1.memory.mem0_store import Mem0Backend

    backend = Mem0Backend(api_key="sk-test")
    fake_client = MagicMock()
    fake_client.add = MagicMock(side_effect=RuntimeError("net"))
    backend._client = fake_client
    backend._enabled = True
    assert await backend.add("text", "u1") is None


# ---------- nats_memory ----------


class _FakeMsg:
    def __init__(self, data: bytes, reply: str | None = None):
        self.data = data
        self.reply = reply


class _FakeNats:
    def __init__(self):
        self.published: list[tuple[str, bytes]] = []
        self.subscribed: list[tuple[str, callable]] = []

    async def subscribe(self, subject, cb):
        self.subscribed.append((subject, cb))

    async def publish(self, subject, payload):
        self.published.append((subject, payload))


class _NoopNats:
    """Captures subscribed callbacks without spawning real futures."""

    def __init__(self):
        self.subscribed: list[tuple[str, callable]] = []
        self.published: list[tuple[str, bytes]] = []

    def subscribe(self, subject, cb):
        # Return a coroutine-like object so `asyncio.ensure_future` accepts it,
        # but record the callback synchronously so tests can drive handlers.
        self.subscribed.append((subject, cb))

        async def _coro():
            return None

        return _coro()

    async def publish(self, subject, payload):
        self.published.append((subject, payload))


async def test_nats_memory_setup_subscribes_two_subjects_and_handlers_work():
    """Run handlers directly after capturing them; bypass ensure_future."""
    import json

    from tier1.memory.nats_memory import setup_memory_nats, SUBJECT_STORE, SUBJECT_RETRIEVE

    nats = _NoopNats()
    backend = AsyncMock()
    backend.store = AsyncMock(return_value="mem-99")
    entry = MagicMock()
    entry.id = "i1"
    entry.content = "c"
    entry.memory_type.value = "episodic"
    backend.search = AsyncMock(return_value=[entry])

    # Patch asyncio.ensure_future inside the nats_memory module so the
    # captured callbacks go on a no-op list instead of being scheduled.
    captured_coros: list = []

    def sink(coro):
        captured_coros.append(coro)
        coro.close()  # don't actually run them
        return MagicMock()

    with patch("asyncio.ensure_future", side_effect=sink):
        setup_memory_nats(nats, backend)

    assert len(nats.subscribed) == 2
    assert nats.subscribed[0][0] == SUBJECT_STORE
    assert nats.subscribed[1][0] == SUBJECT_RETRIEVE

    # Drive the store handler with a happy payload.
    store_cb = nats.subscribed[0][1]
    msg = _FakeMsg(
        json.dumps({"content": "hi", "memory_type": "episodic"}).encode(),
        reply="inbox.1",
    )
    await store_cb(msg)
    backend.store.assert_awaited_once()
    assert ("inbox.1", json.dumps({"id": "mem-99", "ok": True}).encode()) in nats.published

    # Drive retrieve handler.
    retrieve_cb = nats.subscribed[1][1]
    msg2 = _FakeMsg(json.dumps({"query": "q", "top_k": 2}).encode(), reply="inbox.2")
    await retrieve_cb(msg2)
    backend.search.assert_awaited_once()
    assert any(s == "inbox.2" for s, _ in nats.published)


async def test_nats_memory_setup_handles_null_reply_and_exceptions():
    """Handlers should swallow backend errors and skip publish when reply=None."""
    import json

    from tier1.memory.nats_memory import setup_memory_nats

    nats = _NoopNats()
    backend = AsyncMock()
    backend.store = AsyncMock(side_effect=RuntimeError("boom"))
    backend.search = AsyncMock(side_effect=RuntimeError("boom"))

    captured_coros: list = []

    def sink(coro):
        captured_coros.append(coro)
        coro.close()
        return MagicMock()

    with patch("asyncio.ensure_future", side_effect=sink):
        setup_memory_nats(nats, backend)

    store_cb = nats.subscribed[0][1]
    retrieve_cb = nats.subscribed[1][1]

    msg = _FakeMsg(json.dumps({"content": "x"}).encode(), reply=None)
    await store_cb(msg)  # should not raise

    msg2 = _FakeMsg(json.dumps({"query": "x"}).encode(), reply=None)
    await retrieve_cb(msg2)  # should not raise


async def test_nats_memory_store_publishes_when_reply_present_and_results_empty():
    """Retrieve handler should publish an empty list when search returns []."""
    import json

    from tier1.memory.nats_memory import setup_memory_nats

    nats = _NoopNats()
    backend = AsyncMock()
    backend.search = AsyncMock(return_value=[])

    captured_coros: list = []

    def sink(coro):
        captured_coros.append(coro)
        coro.close()
        return MagicMock()

    with patch("asyncio.ensure_future", side_effect=sink):
        setup_memory_nats(nats, backend)

    retrieve_cb = nats.subscribed[1][1]
    msg = _FakeMsg(json.dumps({"query": "x"}).encode(), reply="inbox.3")
    await retrieve_cb(msg)
    assert ("inbox.3", json.dumps({"results": []}).encode()) in nats.published


# ---------- redis (persistence) ----------


async def test_redis_cache_close_when_unconnected():
    from tier1.persistence.redis import RedisCache

    c = RedisCache(url="redis://x", ttl_s=60)
    # client is None; close should be a no-op.
    await c.close()


async def test_redis_cache_close_with_client():
    from tier1.persistence.redis import RedisCache

    c = RedisCache(url="redis://x", ttl_s=60)
    fake = AsyncMock()
    c.client = fake
    await c.close()
    fake.aclose.assert_awaited_once()
    assert c.client is None


async def test_redis_cache_put_state_serializes_payload():
    from tier1.persistence.redis import RedisCache

    c = RedisCache(url="redis://x", ttl_s=60)
    fake = AsyncMock()
    fake.set = AsyncMock(return_value=True)
    c.client = fake
    state = {
        "deliberation_id": "abc",
        "problem": "hi",
        "user_id": "u1",
    }
    await c.put_state(state)  # type: ignore[arg-type]
    args, kwargs = fake.set.call_args
    assert args[0] == "tier1:state:abc"
    assert kwargs["ex"] == 60


async def test_redis_cache_get_state_returns_none_when_unset():
    from tier1.persistence.redis import RedisCache

    c = RedisCache(url="redis://x", ttl_s=60)
    fake = AsyncMock()
    fake.get = AsyncMock(return_value=None)
    c.client = fake
    got = await c.get_state("abc")
    assert got is None


async def test_redis_cache_get_state_returns_parsed_dict():
    import json

    from tier1.persistence.redis import RedisCache

    c = RedisCache(url="redis://x", ttl_s=60)
    payload = json.dumps({"deliberation_id": "abc", "problem": "x"})
    fake = AsyncMock()
    fake.get = AsyncMock(return_value=payload)
    c.client = fake
    got = await c.get_state("abc")
    assert got["deliberation_id"] == "abc"


async def test_redis_cache_drop_state_calls_delete():
    from tier1.persistence.redis import RedisCache

    c = RedisCache(url="redis://x", ttl_s=60)
    fake = AsyncMock()
    fake.delete = AsyncMock(return_value=1)
    c.client = fake
    await c.drop_state("abc")
    fake.delete.assert_awaited_once_with("tier1:state:abc")


# ---------- postgres persistence (close + helpers) ----------


async def test_postgres_pool_close_when_disconnected_is_noop():
    from tier1.persistence.postgres import PostgresPool

    p = PostgresPool(dsn="postgres://x")
    p.pool = None
    await p.close()
    assert p.pool is None


def test_state_to_jsonable_handles_pydantic_models_and_nested():
    """Cover _state_to_jsonable paths (Pydantic, list, dict, primitive)."""
    from tier1.persistence.postgres import _state_to_jsonable

    class _M:
        def model_dump(self):
            return {"a": 1}

    state = {
        "deliberation_id": "id1",
        "problem": "p",
        "user_id": "u",
        "model_field": _M(),
        "list_field": [_M(), "raw"],
        "dict_field": {"k": _M(), "k2": "v"},
        "primitive": 42,
    }
    out = _state_to_jsonable(state)
    assert out["model_field"] == {"a": 1}
    assert out["list_field"] == [{"a": 1}, "raw"]
    assert out["dict_field"] == {"k": {"a": 1}, "k2": "v"}
    assert out["primitive"] == 42


def test_state_from_jsonable_round_trip():
    from tier1.persistence.postgres import _state_from_jsonable

    data = {"deliberation_id": "id1", "problem": "p"}
    assert _state_from_jsonable(data) == data


# ---------- redis_cache (memory layer) ----------


async def test_memory_redis_cache_close_unconnected():
    from tier1.memory.redis_cache import RedisMemoryCache

    c = RedisMemoryCache(url="redis://x", ttl_s=60)
    await c.close()


async def test_memory_redis_cache_close_with_client():
    from tier1.memory.redis_cache import RedisMemoryCache

    c = RedisMemoryCache(url="redis://x", ttl_s=60)
    fake = AsyncMock()
    c.client = fake
    await c.close()
    fake.aclose.assert_awaited_once()
    assert c.client is None


async def test_memory_redis_cache_key_format():
    from tier1.memory.redis_cache import RedisMemoryCache

    c = RedisMemoryCache(url="redis://x", ttl_s=10)
    assert c._key("zzz") == "tier1:memory:zzz"


async def test_memory_redis_cache_set_uses_key_and_default_ttl():
    from tier1.memory import MemoryEntry, MemoryType
    from tier1.memory.redis_cache import RedisMemoryCache

    c = RedisMemoryCache(url="redis://x", ttl_s=99)
    fake = AsyncMock()
    fake.set = AsyncMock(return_value=True)
    c.client = fake
    entry = MemoryEntry(
        id="m1",
        content="hi",
        memory_type=MemoryType.episodic,
        metadata={},
    )
    await c.set("m1", entry)
    args, kwargs = fake.set.call_args
    assert args[0] == "tier1:memory:m1"
    assert kwargs["ex"] == 99


async def test_memory_redis_cache_set_uses_explicit_ttl():
    from tier1.memory import MemoryEntry, MemoryType
    from tier1.memory.redis_cache import RedisMemoryCache

    c = RedisMemoryCache(url="redis://x", ttl_s=99)
    fake = AsyncMock()
    fake.set = AsyncMock(return_value=True)
    c.client = fake
    entry = MemoryEntry(id="m1", content="hi", memory_type=MemoryType.episodic, metadata={})
    await c.set("m1", entry, ttl=5)
    args, kwargs = fake.set.call_args
    assert kwargs["ex"] == 5


async def test_memory_redis_cache_get_returns_none_when_unset():
    from tier1.memory.redis_cache import RedisMemoryCache

    c = RedisMemoryCache(url="redis://x", ttl_s=10)
    fake = AsyncMock()
    fake.get = AsyncMock(return_value=None)
    c.client = fake
    assert await c.get("k") is None


async def test_memory_redis_cache_get_parses_entry():
    import json

    from tier1.memory.redis_cache import RedisMemoryCache

    c = RedisMemoryCache(url="redis://x", ttl_s=10)
    payload = json.dumps(
        {
            "id": "m1",
            "content": "c",
            "memory_type": "episodic",
            "metadata": {},
        }
    )
    fake = AsyncMock()
    fake.get = AsyncMock(return_value=payload)
    c.client = fake
    got = await c.get("m1")
    assert got is not None
    assert got.id == "m1"
    assert got.content == "c"


async def test_memory_redis_cache_delete():
    from tier1.memory.redis_cache import RedisMemoryCache

    c = RedisMemoryCache(url="redis://x", ttl_s=10)
    fake = AsyncMock()
    fake.delete = AsyncMock(return_value=1)
    c.client = fake
    await c.delete("m1")
    fake.delete.assert_awaited_once_with("tier1:memory:m1")
