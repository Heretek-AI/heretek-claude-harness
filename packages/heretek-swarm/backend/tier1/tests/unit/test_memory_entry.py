"""Tests for MemoryEntry and MemoryType."""

from tier1.memory import MemoryBackend, MemoryEntry, MemoryType


def test_memory_type_enum():
    assert MemoryType.episodic == "episodic"
    assert MemoryType.semantic == "semantic"
    assert MemoryType.procedural == "procedural"


def test_memory_entry_defaults():
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic)
    assert entry.id  # auto-generated UUID
    assert entry.content == "test"
    assert entry.memory_type == MemoryType.episodic
    assert entry.embedding is None
    assert entry.metadata == {}
    assert entry.source == ""
    assert entry.deliberation_id is None
    assert entry.agent == ""
    assert entry.created_at  # auto-generated ISO timestamp
    assert entry.ttl_seconds is None


def test_memory_entry_with_options():
    entry = MemoryEntry(
        content="deliberation result",
        memory_type=MemoryType.semantic,
        source="deliberation",
        deliberation_id="did-123",
        agent="alpha",
        ttl_seconds=7200,
    )
    assert entry.source == "deliberation"
    assert entry.deliberation_id == "did-123"
    assert entry.agent == "alpha"
    assert entry.ttl_seconds == 7200
