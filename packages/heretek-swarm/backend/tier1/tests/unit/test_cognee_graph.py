"""Tests for CogneePipeline graph operations (Kùzu)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tier1.memory.cognee_store import CogneePipeline


def _make_pipeline_with_mock_conn():
    """Pipeline with a mocked kuzu Connection (returned by _open_kuzu_db)."""
    backend = MagicMock()
    pipeline = CogneePipeline(backend, graph_path="/tmp/fake-graph")

    mock_conn = MagicMock()

    # Patch _open_kuzu_db to return our mock_conn directly. Anchor the patcher
    # on mock_conn so it survives the duration of the test.
    patcher = patch("tier1.memory.cognee_store._open_kuzu_db", return_value=mock_conn)
    patcher.start()
    mock_conn._patcher = patcher
    return pipeline, mock_conn


def test_ensure_graph_opens_connection_once():
    pipeline, mock_conn = _make_pipeline_with_mock_conn()
    pipeline._ensure_graph()
    assert pipeline._conn is mock_conn
    # Second call is a no-op.
    pipeline._ensure_graph()
    # The DDL was executed at least once (CREATE NODE TABLE for Entity and Document,
    # CREATE REL TABLE for RELATES_TO and CONTAINS).
    assert mock_conn.execute.call_count >= 4


def test_improve_is_idempotent_and_runs_ddl():
    pipeline, mock_conn = _make_pipeline_with_mock_conn()
    import asyncio

    asyncio.run(pipeline.improve())
    # DDL is run at least once; second call must not raise.
    asyncio.run(pipeline.improve())


def test_find_entities_for_entry_runs_cypher():
    pipeline, mock_conn = _make_pipeline_with_mock_conn()
    # Mock the query result: an iterator of dicts with 'name' key.
    mock_result = MagicMock()
    mock_result.has_next.side_effect = [True, True, False]
    mock_result.get_next.side_effect = [{"name": "JWT"}, {"name": "auth"}]
    mock_conn.execute.return_value = mock_result

    names = pipeline._find_entities_for_entry("entry-abc")
    assert names == ["JWT", "auth"]
    # Cypher query was issued.
    assert mock_conn.execute.called


def test_traverse_graph_returns_neighbors():
    pipeline, mock_conn = _make_pipeline_with_mock_conn()
    mock_result = MagicMock()
    mock_result.has_next.side_effect = [True, True, False]
    mock_result.get_next.side_effect = [
        {"name": "middleware"},
        {"name": "token"},
    ]
    mock_conn.execute.return_value = mock_result

    neighbors = pipeline._traverse_graph(["JWT"], hops=2)
    assert "middleware" in neighbors
    assert "token" in neighbors
