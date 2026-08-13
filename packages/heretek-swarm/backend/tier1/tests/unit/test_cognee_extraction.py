"""Tests for CogneePipeline entity/relation extraction."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.memory import MemoryType
from tier1.memory.cognee_store import (
    EXTRACTION_PROMPT,
    CogneePipeline,
    _get_extraction_client,
)


def test_extraction_prompt_format():
    """The prompt must inject the text and demand the exact JSON shape."""
    out = EXTRACTION_PROMPT.format(text="hello world")
    assert "hello world" in out
    assert "entities" in out
    assert "relations" in out
    assert "person|concept|decision|component|metric|event" in out


def test_extract_entities_parses_valid_response():
    pipeline = CogneePipeline(MagicMock())
    response_json = json.dumps(
        {
            "entities": [
                {"name": "JWT", "type": "concept"},
                {"name": "auth", "type": "component"},
            ],
            "relations": [
                {"source": "JWT", "target": "auth", "type": "part_of"},
            ],
        }
    )
    entities, relations = pipeline._extract_entities(response_json)
    assert entities == [
        {"name": "JWT", "type": "concept"},
        {"name": "auth", "type": "component"},
    ]
    assert relations == [
        {"source": "JWT", "target": "auth", "type": "part_of"},
    ]


def test_extract_entities_handles_malformed_json():
    pipeline = CogneePipeline(MagicMock())
    entities, relations = pipeline._extract_entities("not json {")
    assert entities == []
    assert relations == []


def test_extract_entities_drops_unknown_types():
    pipeline = CogneePipeline(MagicMock())
    response_json = json.dumps(
        {
            "entities": [
                {"name": "Good", "type": "concept"},
                {"name": "Bad", "type": "alien_species"},
            ],
            "relations": [
                {"source": "Good", "target": "Bad", "type": "part_of"},
                {"source": "Good", "target": "Bad", "type": "vibes_with"},
            ],
        }
    )
    entities, relations = pipeline._extract_entities(response_json)
    assert len(entities) == 1
    assert entities[0]["name"] == "Good"
    assert len(relations) == 1
    assert relations[0]["type"] == "part_of"


def test_chunk_text_returns_single_chunk():
    """YAGNI: no chunker yet — just one chunk."""
    pipeline = CogneePipeline(MagicMock())
    assert pipeline._chunk_text("hello world") == ["hello world"]


async def test_add_calls_llm_then_writes_graph():
    """add() invokes the openai SDK, parses response, writes nodes/edges, stores memory."""
    backend = MagicMock()
    backend.store = AsyncMock(return_value="entry-id")
    pipeline = CogneePipeline(backend)

    fake_response = MagicMock()
    fake_response.choices = [MagicMock()]
    fake_response.choices[0].message.content = json.dumps(
        {
            "entities": [{"name": "JWT", "type": "concept"}],
            "relations": [],
        }
    )

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)

    mock_conn = MagicMock()
    pipeline._conn = mock_conn

    with patch(
        "tier1.memory.cognee_store._get_extraction_client",
        return_value=fake_client,
    ):
        entry_id = await pipeline.add("JWT is a token format for auth")

    assert entry_id == "entry-id"
    fake_client.chat.completions.create.assert_awaited_once()
    # At least one Cypher write happened (Entity or Document node).
    assert mock_conn.execute.called


async def test_cognify_returns_count_processed():
    """cognify() should run and return an int. Empty graph -> 0."""
    backend = MagicMock()
    pipeline = CogneePipeline(backend)
    pipeline._conn = MagicMock()
    # Mock the unprocessed-documents query to return empty.
    pipeline._conn.execute.return_value.has_next.return_value = False

    count = await pipeline.cognify(batch_size=10)
    assert count == 0


def test_get_extraction_client_anthropic_returns_none():
    """Anthropic uses a different SDK; branch returns None without raising."""
    assert _get_extraction_client("anthropic") is None


def test_get_extraction_client_unknown_returns_none():
    """Unknown providers fall through to the else branch and return None."""
    assert _get_extraction_client("unknown") is None


async def test_add_graph_build_failure_does_not_break():
    """LLM failures during graph build must not break the memory write path."""
    backend = MagicMock()
    backend.store = AsyncMock(return_value="entry-id")
    pipeline = CogneePipeline(backend)

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError("LLM exploded"),
    )

    with patch(
        "tier1.memory.cognee_store._get_extraction_client",
        return_value=fake_client,
    ):
        entry_id = await pipeline.add("payload that fails extraction")

    # Memory backend still received the entry; cognee failure was swallowed.
    assert entry_id == "entry-id"
    backend.store.assert_awaited_once()
    stored = backend.store.await_args.args[0]
    assert stored.content == "payload that fails extraction"
