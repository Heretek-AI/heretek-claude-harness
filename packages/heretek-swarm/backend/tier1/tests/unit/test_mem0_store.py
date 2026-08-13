"""Tests for Mem0Backend."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.memory.mem0_store import Mem0Backend


def test_disabled_backend():
    backend = Mem0Backend(api_key=None)
    assert not backend._enabled


async def test_add_returns_none_when_disabled():
    backend = Mem0Backend(api_key=None)
    result = await backend.add("test", user_id="agent1")
    assert result is None


async def test_add_calls_client():
    backend = Mem0Backend(api_key="test-key")
    mock_client = MagicMock()
    mock_client.add = MagicMock(return_value={"id": "mem-123"})
    backend._client = mock_client
    result = await backend.add("test memory", user_id="agent1")
    mock_client.add.assert_called_once()
    assert result == "mem-123"


async def test_search_returns_empty_when_disabled():
    backend = Mem0Backend(api_key=None)
    result = await backend.search("query", user_id="agent1")
    assert result == []


async def test_delete_returns_false_when_disabled():
    backend = Mem0Backend(api_key=None)
    result = await backend.delete("mem-123")
    assert result is False


# ---------------------------------------------------------------------------
# Coverage extension: enabled-backend paths (client construction + ops + errors)
# ---------------------------------------------------------------------------


def _make_enabled_backend(monkeypatch) -> Mem0Backend:
    """Mem0Backend with _enabled=True, _client pre-wired to a MagicMock.

    Avoids the lazy import inside _ensure_client by setting _client directly.
    """
    backend = Mem0Backend(api_key="test-key")
    # Patch _ensure_client so the real `from mem0ai import MemoryClient` branch
    # does not execute — we control _client ourselves.
    monkeypatch.setattr(backend, "_ensure_client", lambda: None)
    backend._client = MagicMock()
    return backend


def test_init_with_key_enables_backend():
    backend = Mem0Backend(api_key="sk-anything")
    assert backend._enabled is True
    assert backend._api_key == "sk-anything"
    assert backend._vector_store == "qdrant"


def test_ensure_client_lazy_imports_memory_client(monkeypatch):
    """First call to _ensure_client with enabled=True imports MemoryClient."""
    import sys

    backend = Mem0Backend(api_key="k")
    fake_client_instance = MagicMock(name="client-instance")
    fake_memory_client = MagicMock(return_value=fake_client_instance)
    fake_mem0ai = MagicMock()
    fake_mem0ai.MemoryClient = fake_memory_client
    monkeypatch.setitem(sys.modules, "mem0ai", fake_mem0ai)
    backend._ensure_client()
    fake_memory_client.assert_called_once_with(api_key="k")
    assert backend._client is fake_client_instance
    # Second call is a no-op (client is already set).
    backend._ensure_client()
    fake_memory_client.assert_called_once()


async def test_add_returns_id_from_client(monkeypatch):
    backend = _make_enabled_backend(monkeypatch)
    backend._client.add = MagicMock(return_value={"id": "mem-xyz"})
    result = await backend.add("hi", user_id="u1", metadata={"k": "v"})
    backend._client.add.assert_called_once_with("hi", user_id="u1", metadata={"k": "v"})
    assert result == "mem-xyz"


async def test_add_passes_empty_metadata_when_none(monkeypatch):
    backend = _make_enabled_backend(monkeypatch)
    backend._client.add = MagicMock(return_value={"id": "m1"})
    await backend.add("hi", user_id="u1", metadata=None)
    args = backend._client.add.call_args
    assert args.kwargs["metadata"] == {}


async def test_add_returns_none_on_exception(monkeypatch):
    backend = _make_enabled_backend(monkeypatch)
    backend._client.add = MagicMock(side_effect=RuntimeError("network down"))
    result = await backend.add("hi", user_id="u1")
    assert result is None


async def test_search_returns_results_when_dict(monkeypatch):
    backend = _make_enabled_backend(monkeypatch)
    backend._client.search = MagicMock(return_value={"results": [{"id": "a"}, {"id": "b"}]})
    result = await backend.search("q", user_id="u1", top_k=2)
    backend._client.search.assert_called_once_with("q", user_id="u1", limit=2)
    assert result == [{"id": "a"}, {"id": "b"}]


async def test_search_returns_list_when_non_dict(monkeypatch):
    backend = _make_enabled_backend(monkeypatch)
    backend._client.search = MagicMock(return_value=[{"id": "x"}])
    result = await backend.search("q", user_id="u1")
    assert result == [{"id": "x"}]


async def test_search_returns_empty_on_exception(monkeypatch):
    backend = _make_enabled_backend(monkeypatch)
    backend._client.search = MagicMock(side_effect=ValueError("api down"))
    result = await backend.search("q", user_id="u1")
    assert result == []


async def test_update_returns_true_on_success(monkeypatch):
    backend = _make_enabled_backend(monkeypatch)
    backend._client.update = MagicMock(return_value="ok")
    result = await backend.update("mem-1", "new text")
    backend._client.update.assert_called_once_with("mem-1", "new text")
    assert result is True


async def test_update_returns_false_on_exception(monkeypatch):
    backend = _make_enabled_backend(monkeypatch)
    backend._client.update = MagicMock(side_effect=RuntimeError("fail"))
    result = await backend.update("mem-1", "new text")
    assert result is False


async def test_delete_returns_true_on_success(monkeypatch):
    backend = _make_enabled_backend(monkeypatch)
    backend._client.delete = MagicMock(return_value=None)
    result = await backend.delete("mem-1")
    backend._client.delete.assert_called_once_with("mem-1")
    assert result is True


async def test_delete_returns_false_on_exception(monkeypatch):
    backend = _make_enabled_backend(monkeypatch)
    backend._client.delete = MagicMock(side_effect=RuntimeError("boom"))
    result = await backend.delete("mem-1")
    assert result is False


async def test_disabled_short_circuits_all_ops():
    """api_key=None must not invoke any client code paths."""
    backend = Mem0Backend(api_key=None)
    # No _client attribute manipulation — disabled branches must short-circuit.
    assert await backend.add("x", user_id="u") is None
    assert await backend.search("x", user_id="u") == []
    assert await backend.update("m", "t") is False
    assert await backend.delete("m") is False
