"""Unit tests for tier1.persistence.qdrant.

All QdrantClient interactions are mocked; no real qdrant is contacted.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tier1.persistence.qdrant import QdrantStore


def test_init_stores_url_and_collection_and_none_client() -> None:
    s = QdrantStore(url="http://q:6333", collection="tier1_memory")
    assert s.url == "http://q:6333"
    assert s.collection == "tier1_memory"
    assert s.client is None


def test_init_default_collection_is_string_and_client_none() -> None:
    s = QdrantStore(url="u", collection="c")
    assert isinstance(s.collection, str)
    assert s.client is None


def test_connect_constructs_qdrant_client_with_url() -> None:
    fake_client_cls = MagicMock()
    fake_instance = MagicMock()
    fake_client_cls.return_value = fake_instance

    with patch("tier1.persistence.qdrant.QdrantClient", fake_client_cls):
        s = QdrantStore(url="http://q:6333", collection="c")
        s.connect()

    fake_client_cls.assert_called_once_with(url="http://q:6333")
    assert s.client is fake_instance


def test_connect_called_twice_creates_two_clients() -> None:
    fake_client_cls = MagicMock()
    fake_client_cls.return_value = MagicMock()
    with patch("tier1.persistence.qdrant.QdrantClient", fake_client_cls):
        s = QdrantStore(url="u", collection="c")
        s.connect()
        s.connect()
    assert fake_client_cls.call_count == 2


def test_close_noop_when_client_none() -> None:
    s = QdrantStore(url="u", collection="c")
    s.client = None
    # Should not raise
    s.close()
    assert s.client is None


def test_close_calls_client_close_and_clears() -> None:
    s = QdrantStore(url="u", collection="c")
    fake = MagicMock()
    s.client = fake
    s.close()
    fake.close.assert_called_once_with()
    assert s.client is None


def test_close_swallows_client_close_exception() -> None:
    """close() must swallow exceptions from client.close() (noqa: BLE001)."""
    s = QdrantStore(url="u", collection="c")
    fake = MagicMock()
    fake.close.side_effect = RuntimeError("boom")
    s.client = fake
    s.close()  # Should not raise
    assert s.client is None


def test_close_swallows_attribute_error() -> None:
    s = QdrantStore(url="u", collection="c")
    fake = MagicMock()
    fake.close.side_effect = AttributeError("nope")
    s.client = fake
    s.close()
    assert s.client is None


def test_health_returns_true_on_success() -> None:
    s = QdrantStore(url="u", collection="c")
    fake = MagicMock()
    fake.get_collections.return_value = MagicMock()
    s.client = fake

    assert s.health() is True
    fake.get_collections.assert_called_once_with()


def test_health_propagates_get_collections_failure() -> None:
    s = QdrantStore(url="u", collection="c")
    fake = MagicMock()
    fake.get_collections.side_effect = ConnectionError("down")
    s.client = fake
    with pytest.raises(ConnectionError, match="down"):
        s.health()


def test_health_asserts_client_set() -> None:
    s = QdrantStore(url="u", collection="c")
    s.client = None
    with pytest.raises(AssertionError):
        s.health()


def test_health_called_after_close_raises() -> None:
    s = QdrantStore(url="u", collection="c")
    fake = MagicMock()
    fake.get_collections.return_value = MagicMock()
    with patch("tier1.persistence.qdrant.QdrantClient", return_value=fake):
        s.connect()
    s.close()
    with pytest.raises(AssertionError):
        s.health()
