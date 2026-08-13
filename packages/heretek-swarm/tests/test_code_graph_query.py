"""
Tests for the code_graph_query tool.

Per M-arch PR #9: verify the code-review-graph query tool can be
instantiated, reads from a real SQLite DB, and handles missing DBs
gracefully. The full action set is exercised in
tests/test_code_graph_query.py.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from heretek_swarm.tools.base import ToolContext, ToolStatus
from heretek_swarm.tools.code_graph_query import (
    DEFAULT_DB_PATH,
    CodeGraphQueryTool,
    get_graph_summary,
    query_node,
    resolve_db_path,
)

SCHEMA = """
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    language TEXT,
    parent_name TEXT,
    params TEXT,
    return_type TEXT,
    modifiers TEXT,
    is_test INTEGER DEFAULT 0,
    file_hash TEXT,
    extra TEXT DEFAULT '{}',
    updated_at REAL NOT NULL
);
CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    source_qualified TEXT NOT NULL,
    target_qualified TEXT NOT NULL,
    file_path TEXT NOT NULL,
    line INTEGER DEFAULT 0,
    extra TEXT DEFAULT '{}',
    confidence REAL DEFAULT 1.0,
    confidence_tier TEXT DEFAULT 'EXTRACTED',
    updated_at REAL NOT NULL
);
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


@pytest.fixture
def graph_db(tmp_path: Path) -> Path:
    """Build a temp code-review-graph DB with a few sample nodes."""
    db = tmp_path / "graph.db"
    with sqlite3.connect(str(db)) as conn:
        conn.executescript(SCHEMA)
        import time

        now = time.time()
        conn.executemany(
            "INSERT INTO nodes (kind, name, qualified_name, file_path, line_start, line_end, language, parent_name, is_test, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("File", "rag.py", "rag.py", "rag.py", 1, 500, "python", None, 0, now),
                ("Class", "RAGPipeline", "rag.RAGPipeline", "rag.py", 100, 500, "python", "rag.py", 0, now),
                ("Function", "query", "rag.RAGPipeline.query", "rag.py", 310, 400, "python", "rag.RAGPipeline", 0, now),
            ],
        )
        conn.execute(
            "INSERT INTO edges (kind, source_qualified, target_qualified, file_path, line, confidence, confidence_tier, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("CALLS", "rag.RAGPipeline.query", "_hybrid_retrieve", "rag.py", 355, 0.95, "EXTRACTED", now),
        )
    return db


@pytest.fixture
def ctx() -> ToolContext:
    return ToolContext(agent_id="coder-1", session_id="s1")


class TestResolveDbPath:
    def test_default_path_points_to_code_review_graph(self) -> None:
        """Default path is the repo's .code-review-graph/graph.db."""
        assert str(resolve_db_path()).endswith(".code-review-graph/graph.db")
        assert str(DEFAULT_DB_PATH).endswith(".code-review-graph/graph.db")

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CODE_GRAPH_DB_PATH env var overrides the default."""
        monkeypatch.setenv("CODE_GRAPH_DB_PATH", "/tmp/custom.db")
        assert str(resolve_db_path()) == "/tmp/custom.db"


class TestQueryNode:
    def test_existing_node(self, graph_db: Path) -> None:
        """query_node returns the row for a known qualified_name."""
        result = query_node("rag.RAGPipeline", db_path=graph_db)
        assert result["available"] is True
        assert result["node"]["name"] == "RAGPipeline"
        assert result["node"]["kind"] == "Class"

    def test_missing_node(self, graph_db: Path) -> None:
        """query_node returns node=None for non-existent names."""
        result = query_node("nope.nada", db_path=graph_db)
        assert result["available"] is True
        assert result["node"] is None

    def test_missing_db(self, tmp_path: Path) -> None:
        """query_node returns available=False when DB is missing."""
        result = query_node("anything", db_path=tmp_path / "nope.db")
        assert result["available"] is False
        assert result["node"] is None


class TestGetGraphSummary:
    def test_counts(self, graph_db: Path) -> None:
        """get_graph_summary returns correct node/edge counts and breakdowns."""
        result = get_graph_summary(db_path=graph_db)
        assert result["available"] is True
        assert result["node_total"] == 3
        assert result["edge_total"] == 1
        kinds = {row["kind"]: row["n"] for row in result["node_kinds"]}
        assert kinds == {"File": 1, "Class": 1, "Function": 1}

    def test_missing_db(self, tmp_path: Path) -> None:
        """get_graph_summary returns available=False when DB is missing."""
        result = get_graph_summary(db_path=tmp_path / "nope.db")
        assert result["available"] is False


class TestCodeGraphQueryTool:
    def test_tool_metadata(self) -> None:
        """Tool has the expected name, category, and tags."""
        tool = CodeGraphQueryTool()
        assert tool.name == "code_graph_query"
        assert tool.metadata.category == "code_intelligence"
        assert "codelookup" in tool.metadata.tags

    def test_default_db_path(self) -> None:
        """The tool's default DB path points to .code-review-graph/graph.db."""
        tool = CodeGraphQueryTool()
        assert str(tool._db_path).endswith(".code-review-graph/graph.db")

    def test_explicit_db_path(self, graph_db: Path) -> None:
        """The tool respects an explicit db_path override."""
        tool = CodeGraphQueryTool(db_path=graph_db)
        assert tool._db_path == graph_db

    @pytest.mark.asyncio
    async def test_node_action(self, graph_db: Path, ctx) -> None:
        """Tool dispatches op=query_node correctly."""
        tool = CodeGraphQueryTool(db_path=graph_db)
        result = await tool.execute(
            ctx, op="query_node", qualified_name="rag.RAGPipeline"
        )
        assert result.status == ToolStatus.SUCCESS
        assert result.output["node"]["name"] == "RAGPipeline"

    @pytest.mark.asyncio
    async def test_get_graph_summary_action(self, graph_db: Path, ctx) -> None:
        """Tool dispatches op=get_graph_summary correctly."""
        tool = CodeGraphQueryTool(db_path=graph_db)
        result = await tool.execute(ctx, op="get_graph_summary")
        assert result.status == ToolStatus.SUCCESS
        assert result.output["node_total"] == 3

    @pytest.mark.asyncio
    async def test_unknown_op_returns_failed(self, ctx) -> None:
        """Unknown op returns ToolStatus.FAILED with an error message."""
        tool = CodeGraphQueryTool()
        result = await tool.execute(ctx, op="bogus")
        assert result.status == ToolStatus.FAILED
        assert "Unknown op" in result.error

    @pytest.mark.asyncio
    async def test_missing_kwarg_returns_failed(self, ctx) -> None:
        """Missing required kwarg returns ToolStatus.FAILED."""
        tool = CodeGraphQueryTool()
        result = await tool.execute(ctx, op="query_node")
        assert result.status == ToolStatus.FAILED
        assert "Missing" in result.error

    @pytest.mark.asyncio
    async def test_missing_db_returns_failed(self, tmp_path: Path, ctx) -> None:
        """Missing DB returns ToolStatus.FAILED with a clear error message."""
        tool = CodeGraphQueryTool(db_path=tmp_path / "nope.db")
        result = await tool.execute(
            ctx, op="query_node", qualified_name="any.thing"
        )
        assert result.status == ToolStatus.FAILED
        assert "code-graph DB unavailable" in result.error
        assert "nope.db" in result.error

    @pytest.mark.asyncio
    async def test_corrupt_db_returns_failed(self, tmp_path: Path, ctx) -> None:
        """Corrupt DB returns ToolStatus.FAILED."""
        bad = tmp_path / "bad.db"
        bad.write_text("not a sqlite db")
        tool = CodeGraphQueryTool(db_path=bad)
        result = await tool.execute(ctx, op="get_graph_summary")
        assert result.status == ToolStatus.FAILED
