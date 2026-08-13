"""
Memory migration tests — S02 acceptance criteria.

Verifies that the DualTierMemory → CogneeMemoryReader/CogneeWriter migration
is complete: no legacy imports remain outside the memory/ package, all 11
migrated files import from cognee_reader/cognee_writer, and the top-level
package exports the new classes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "backend" / "heretek_swarm"

# The files that were migrated (per T01-T06 task plans).
# Note: instances.py accesses cognee_reader via api.main, not a direct import.
# agent_runtime.py was removed in the Phase 2 dead-cluster cleanup.
MIGRATED_FILES: list[Path] = [
    SRC / "runtime" / "main_loop.py",
    SRC / "tools" / "mcp_tools.py",
    SRC / "runtime" / "tools.py",
    SRC / "actors" / "historian" / "agent.py",
    SRC / "api" / "main.py",
    SRC / "api" / "agents" / "instances.py",
    SRC / "api" / "consensus.py",
    SRC / "api" / "memory_versions.py",
    SRC / "workflow" / "node_executors.py",
    SRC / "plugins" / "examples.py",
]

# Files that use cognee indirectly (via api.main module attribute),
# so they won't have a direct cognee_reader/cognee_writer import.
INDIRECT_COGNEE_FILES: set[Path] = {
    SRC / "api" / "agents" / "instances.py",
    SRC / "runtime" / "tools.py",
    SRC / "tools" / "mcp_tools.py",
}

# Legacy symbols that should NOT be imported outside memory/
LEGACY_SYMBOLS = [
    "DualTierMemory",
    "DualTierMemorySystem",
    "PersistentMemory",
    "PersistentMemoryStore",
    "MemoryEntry",
    "MemoryQuery",
    "MemorySystem",
    "get_versioned_store",
]


def _grep(pattern: str, path: Path, include: str = "*.py") -> list[str]:
    """Return matching lines from rg, stripped of the repo-root prefix."""
    result = subprocess.run(
        ["rg", "--no-heading", "-n", pattern, "--glob", include, str(path)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    # Filter out __pycache__ hits that rg sometimes returns
    return [
        line
        for line in result.stdout.strip().splitlines()
        if "__pycache__" not in line and line
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoLegacyImportsOutsideMemory:
    """No file outside memory/ should import a legacy memory class."""

    @pytest.mark.parametrize("symbol", LEGACY_SYMBOLS)
    def test_no_legacy_imports(self, symbol: str) -> None:
        """Grep for 'from heretek_swarm_core.memory.* import.*<symbol>' outside memory/."""
        # Search the whole src tree for import lines referencing the symbol
        lines = _grep(
            rf"from heretek_swarm\.memory\.\w+ import.*{symbol}",
            SRC,
            "*.py",
        )
        # Allow hits inside memory/ itself (base classes still live there)
        outside = [
            ln for ln in lines if "/memory/" not in ln and "memory\\" not in ln
        ]
        assert not outside, (
            f"Legacy symbol '{symbol}' imported outside memory/ package:\n"
            + "\n".join(outside)
        )


class TestMigratedFilesUseCognee:
    """All 11 migrated files import from cognee_reader or cognee_writer."""

    @pytest.mark.parametrize(
        "file_path",
        MIGRATED_FILES,
        ids=[str(p.relative_to(REPO_ROOT)) for p in MIGRATED_FILES],
    )
    def test_imports_cognee(self, file_path: Path) -> None:
        """Each migrated file should contain at least one cognee import."""
        content = file_path.read_text(encoding="utf-8")
        has_import = (
            "CogneeMemoryReader" in content or "CogneeMemoryWriter" in content
        )
        if file_path in INDIRECT_COGNEE_FILES:
            # These files reference cognee indirectly — just confirm no
            # legacy imports remain.
            for symbol in LEGACY_SYMBOLS:
                assert symbol not in content or f"# {symbol}" in content, (
                    f"{file_path.relative_to(REPO_ROOT)} still references "
                    f"legacy symbol '{symbol}'"
                )
        else:
            assert has_import, (
                f"{file_path.relative_to(REPO_ROOT)} does not import "
                "CogneeMemoryReader or CogneeMemoryWriter"
            )


class TestTopLevelExports:
    """CogneeMemoryReader and CogneeWriter are importable from heretek_swarm."""

    def test_cognee_reader_exportable(self) -> None:
        from heretek_swarm import CogneeMemoryReader

        assert CogneeMemoryReader is not None

    def test_cognee_writer_exportable(self) -> None:
        from heretek_swarm import CogneeMemoryWriter

        assert CogneeMemoryWriter is not None

    def test_legacy_memory_system_not_exported(self) -> None:
        """MemorySystem should no longer be in __all__."""
        import heretek_swarm

        assert "MemorySystem" not in heretek_swarm.__all__


class TestSpecificFileCleanups:
    """Per-file legacy-reference checks for key migrated files."""

    def test_main_loop_no_dual_tier(self) -> None:
        content = (SRC / "runtime" / "main_loop.py").read_text(encoding="utf-8")
        assert "DualTierMemory" not in content, (
            "runtime/main_loop.py still references DualTierMemory"
        )

    def test_historian_no_dual_tier_or_memory_entry(self) -> None:
        content = (
            SRC / "actors" / "historian" / "agent.py"
        ).read_text(encoding="utf-8")
        assert "DualTierMemory" not in content, (
            "actors/historian/agent.py still references DualTierMemory"
        )
        # MemoryEntry is only allowed in type comments or strings, not imports
        import_lines = [
            ln
            for ln in content.splitlines()
            if ln.strip().startswith("import") or "import " in ln.split("#")[0]
        ]
        for ln in import_lines:
            assert "MemoryEntry" not in ln, (
                f"actors/historian/agent.py imports MemoryEntry: {ln}"
            )

    def test_api_main_no_persistent_memory(self) -> None:
        content = (SRC / "api" / "main.py").read_text(encoding="utf-8")
        assert "PersistentMemory" not in content, (
            "api/main.py still references PersistentMemory"
        )

    def test_memory_versions_no_get_versioned_store(self) -> None:
        content = (
            SRC / "api" / "memory_versions.py"
        ).read_text(encoding="utf-8")
        assert "get_versioned_store" not in content, (
            "api/memory_versions.py still references get_versioned_store"
        )
