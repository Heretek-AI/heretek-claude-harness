"""
code_graph_query - tool for querying the local code-review-graph SQLite DB.

M-arch PR #9: wire code-review-graph into the Coder agent's tool
registry. The local ``.code-review-graph/graph.db`` is a SQLite file
maintained by the code-review-graph builder. This module exposes
query helpers that the Coder agent can call to look up call graphs,
inheritance, and imports without leaving the runtime.

Schema (from .code-review-graph/graph.db):
  nodes(id, kind, name, qualified_name, file_path, line_start,
        line_end, language, parent_name, params, return_type,
        modifiers, is_test, file_hash, extra, updated_at)
  edges(id, kind, source_qualified, target_qualified, file_path,
        line, extra, confidence, confidence_tier, updated_at)

If the DB file is missing or corrupt, the tool returns a
``ToolExecutionResult`` with status FAILED and a clear error
message. The tool never raises to the caller.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import structlog

from heretek_swarm.tools.base import (
    BaseTool,
    ToolContext,
    ToolExecutionResult,
    ToolMetadata,
    ToolStatus,
)

logger = structlog.get_logger(__name__)


def _default_db_path() -> Path:
    """Return the default code-review-graph DB path (repo root + .code-review-graph/graph.db)."""
    return Path(__file__).resolve().parents[3] / ".code-review-graph" / "graph.db"


DEFAULT_DB_PATH: Path = _default_db_path()


def resolve_db_path() -> Path:
    """Resolve the code-review-graph DB path from env or default."""
    env_path = os.getenv("CODE_GRAPH_DB_PATH")
    return Path(env_path) if env_path else _default_db_path()


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with row_factory=Row."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def query_node(qualified_name: str, db_path: Path | None = None) -> dict[str, Any]:
    """Look up a single node by exact qualified_name."""
    resolved = db_path or resolve_db_path()
    if not resolved.exists():
        return {"available": False, "db_path": str(resolved), "node": None}
    with _connect(resolved) as conn:
        cur = conn.execute(
            "SELECT * FROM nodes WHERE qualified_name = ?",
            (qualified_name,),
        )
        row = cur.fetchone()
    return {
        "available": True,
        "db_path": str(resolved),
        "node": dict(row) if row else None,
    }


def search_nodes(
    name_pattern: str,
    *,
    kind: str | None = None,
    limit: int = 25,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Search nodes by name (LIKE) with optional kind filter."""
    resolved = db_path or resolve_db_path()
    if not resolved.exists():
        return {
            "available": False,
            "db_path": str(resolved),
            "count": 0,
            "hits": [],
        }
    with _connect(resolved) as conn:
        if kind:
            cur = conn.execute(
                "SELECT kind, name, qualified_name, file_path, line_start "
                "FROM nodes WHERE name LIKE ? AND kind = ? "
                "ORDER BY name LIMIT ?",
                (f"%{name_pattern}%", kind, limit),
            )
        else:
            cur = conn.execute(
                "SELECT kind, name, qualified_name, file_path, line_start "
                "FROM nodes WHERE name LIKE ? "
                "ORDER BY name LIMIT ?",
                (f"%{name_pattern}%", limit),
            )
        hits = [dict(row) for row in cur.fetchall()]
    return {
        "available": True,
        "db_path": str(resolved),
        "count": len(hits),
        "hits": hits,
    }


def query_callers(qualified_name: str, db_path: Path | None = None) -> dict[str, Any]:
    """List edges where source_qualified calls this node."""
    resolved = db_path or resolve_db_path()
    if not resolved.exists():
        return {
            "available": False,
            "db_path": str(resolved),
            "count": 0,
            "callers": [],
        }
    with _connect(resolved) as conn:
        cur = conn.execute(
            "SELECT source_qualified, kind, file_path, line, confidence "
            "FROM edges WHERE target_qualified = ? AND kind = 'CALLS' "
            "ORDER BY confidence DESC LIMIT 100",
            (qualified_name,),
        )
        rows = [dict(row) for row in cur.fetchall()]
    return {
        "available": True,
        "db_path": str(resolved),
        "count": len(rows),
        "callers": rows,
    }


def query_callees(qualified_name: str, db_path: Path | None = None) -> dict[str, Any]:
    """List edges where this node calls other nodes."""
    resolved = db_path or resolve_db_path()
    if not resolved.exists():
        return {
            "available": False,
            "db_path": str(resolved),
            "count": 0,
            "callees": [],
        }
    with _connect(resolved) as conn:
        cur = conn.execute(
            "SELECT target_qualified, kind, file_path, line, confidence "
            "FROM edges WHERE source_qualified = ? AND kind = 'CALLS' "
            "ORDER BY confidence DESC LIMIT 100",
            (qualified_name,),
        )
        rows = [dict(row) for row in cur.fetchall()]
    return {
        "available": True,
        "db_path": str(resolved),
        "count": len(rows),
        "callees": rows,
    }


def query_file_imports(file_path: str, db_path: Path | None = None) -> dict[str, Any]:
    """List IMPORTS_FROM edges where the source file is the given path."""
    resolved = db_path or resolve_db_path()
    if not resolved.exists():
        return {
            "available": False,
            "db_path": str(resolved),
            "count": 0,
            "imports": [],
        }
    with _connect(resolved) as conn:
        cur = conn.execute(
            "SELECT target_qualified, line, confidence "
            "FROM edges WHERE file_path = ? AND kind = 'IMPORTS_FROM' "
            "ORDER BY line LIMIT 200",
            (file_path,),
        )
        rows = [dict(row) for row in cur.fetchall()]
    return {
        "available": True,
        "db_path": str(resolved),
        "count": len(rows),
        "imports": rows,
    }


def query_inheritance(qualified_name: str, db_path: Path | None = None) -> dict[str, Any]:
    """List INHERITS edges where the source is the given class."""
    resolved = db_path or resolve_db_path()
    if not resolved.exists():
        return {
            "available": False,
            "db_path": str(resolved),
            "count": 0,
            "bases": [],
        }
    with _connect(resolved) as conn:
        cur = conn.execute(
            "SELECT target_qualified, file_path, line "
            "FROM edges WHERE source_qualified = ? AND kind = 'INHERITS' "
            "ORDER BY target_qualified",
            (qualified_name,),
        )
        rows = [dict(row) for row in cur.fetchall()]
    return {
        "available": True,
        "db_path": str(resolved),
        "count": len(rows),
        "bases": rows,
    }


def query_metadata(db_path: Path | None = None) -> dict[str, Any]:
    """Return all key/value pairs from the metadata table."""
    resolved = db_path or resolve_db_path()
    if not resolved.exists():
        return {
            "available": False,
            "db_path": str(resolved),
            "count": 0,
            "metadata": [],
        }
    with _connect(resolved) as conn:
        cur = conn.execute("SELECT key, value FROM metadata")
        rows = [dict(row) for row in cur.fetchall()]
    return {
        "available": True,
        "db_path": str(resolved),
        "count": len(rows),
        "metadata": rows,
    }


def get_graph_summary(db_path: Path | None = None) -> dict[str, Any]:
    """Return high-level stats: node_total, edge_total, kind breakdowns."""
    resolved = db_path or resolve_db_path()
    if not resolved.exists():
        return {"available": False, "db_path": str(resolved)}
    with _connect(resolved) as conn:
        node_total = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edge_total = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        node_kinds = [
            dict(row)
            for row in conn.execute(
                "SELECT kind, COUNT(*) AS n FROM nodes GROUP BY kind ORDER BY n DESC"
            ).fetchall()
        ]
        edge_kinds = [
            dict(row)
            for row in conn.execute(
                "SELECT kind, COUNT(*) AS n FROM edges GROUP BY kind ORDER BY n DESC"
            ).fetchall()
        ]
    return {
        "available": True,
        "db_path": str(resolved),
        "node_total": node_total,
        "edge_total": edge_total,
        "node_kinds": node_kinds,
        "edge_kinds": edge_kinds,
    }


class CodeGraphQueryTool(BaseTool):
    """Tool that queries the local code-review-graph DB.

    All methods return ``{"available": false, ...}`` when the DB
    is missing, so callers can detect a fresh-clone state without
    exception handling.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        super().__init__(
            name="code_graph_query",
            description=(
                "Query the local code-review-graph DB for symbols, "
                "callers, callees, imports, and metadata. Returns "
                "{available: false, ...} when the DB hasn't been built."
            ),
        )
        self.metadata = ToolMetadata(
            name="code_graph_query",
            description=self.description,
            category="code_intelligence",
            tags=["codelookup", "static-analysis", "code-review-graph"],
            version="1.0.0",
        )
        self._db_path = db_path if db_path is not None else resolve_db_path()

    async def execute(self, _context: ToolContext, **kwargs: Any) -> ToolExecutionResult:
        """Dispatch to the right query method based on the ``op`` kwarg.

        Supported ops:
            - ``query_node`` (kwargs: ``qualified_name``)
            - ``search_nodes`` (kwargs: ``name_pattern``, optional ``kind``, ``limit``)
            - ``query_callers`` (kwargs: ``qualified_name``)
            - ``query_callees`` (kwargs: ``qualified_name``)
            - ``query_file_imports`` (kwargs: ``file_path``)
            - ``query_inheritance`` (kwargs: ``qualified_name``)
            - ``query_metadata`` (no extra kwargs)
            - ``get_graph_summary`` (no extra kwargs)
        """
        if not self._db_path.exists():
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error=(
                    f"code-graph DB unavailable at {self._db_path}. "
                    "Run the code-review-graph builder or set "
                    "CODE_GRAPH_DB_PATH to a valid SQLite file."
                ),
            )
        op = kwargs.get("op")
        if not self._db_path.exists():
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error=(
                    f"code-graph DB unavailable at {self._db_path}. "
                    "Run the code-review-graph builder or set "
                    "CODE_GRAPH_DB_PATH to a valid SQLite file."
                ),
            )
        try:
            if op == "query_node":
                out = query_node(kwargs["qualified_name"], self._db_path)
            elif op == "search_nodes":
                out = search_nodes(
                    kwargs["name_pattern"],
                    kind=kwargs.get("kind"),
                    limit=kwargs.get("limit", 25),
                    db_path=self._db_path,
                )
            elif op == "query_callers":
                out = query_callers(kwargs["qualified_name"], self._db_path)
            elif op == "query_callees":
                out = query_callees(kwargs["qualified_name"], self._db_path)
            elif op == "query_file_imports":
                out = query_file_imports(kwargs["file_path"], self._db_path)
            elif op == "query_inheritance":
                out = query_inheritance(kwargs["qualified_name"], self._db_path)
            elif op == "query_metadata":
                out = query_metadata(self._db_path)
            elif op == "get_graph_summary":
                out = get_graph_summary(self._db_path)
            else:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status=ToolStatus.FAILED,
                    error=f"Unknown op: {op!r}",
                )
        except KeyError as e:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error=f"Missing required kwarg: {e}",
            )
        except (OSError, sqlite3.DatabaseError) as e:
            logger.warning(
                "code_graph_query_db_error",
                db_path=str(self._db_path),
                error=str(e),
            )
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                error=(
                    f"code-graph DB unavailable at {self._db_path}: {e}. "
                    "Run the code-review-graph builder or set "
                    "CODE_GRAPH_DB_PATH to a valid SQLite file."
                ),
            )
        return ToolExecutionResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output=out,
        )
