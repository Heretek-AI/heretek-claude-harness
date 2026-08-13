"""
Tests for the research/ tier namespace.

Per M-arch PR #8: verify the research package re-exports the
consciousness and collective modules correctly. New code should
import from heretek_swarm.research; existing imports from the
legacy locations continue to work.
"""

from __future__ import annotations

import importlib
import inspect
import os

import pytest

CONSCIOUSNESS_MODULES = [
    "iit_phi",
    "iit",
    "gwt",
    "gwt_deliberation",
    "fep",
    "fep_active_inference",
    "self_model",
    "introspection",
    "ast",
]

COLLECTIVE_MODULES = [
    "emergent_detection",
    "emergent_detection_types",
    "emergence_analyzer",
    "evolution_engine",
    "agency_tracking",
]


@pytest.fixture
def research():
    return importlib.import_module("heretek_swarm.research")


@pytest.fixture
def research_dir():
    return os.path.join(
        os.path.dirname(__file__),
        "..",
        "backend",
        "heretek_swarm",
        "research",
    )


class TestResearchPackageImports:
    def test_consciousness_modules_reexported(self, research) -> None:
        """All 9 consciousness modules re-exported as attributes."""
        assert hasattr(research, "iit_phi")
        assert hasattr(research, "iit")
        assert hasattr(research, "gwt")
        assert hasattr(research, "gwt_deliberation")
        assert hasattr(research, "fep")
        assert hasattr(research, "fep_active_inference")
        assert hasattr(research, "self_model")
        assert hasattr(research, "introspection")
        assert hasattr(research, "ast")

    def test_collective_modules_reexported(self, research) -> None:
        """All 5 collective modules re-exported as attributes."""
        assert hasattr(research, "emergent_detection")
        assert hasattr(research, "emergent_detection_types")
        assert hasattr(research, "emergence_analyzer")
        assert hasattr(research, "evolution_engine")
        assert hasattr(research, "agency_tracking")

    def test_reexports_are_same_module_objects(self, research) -> None:
        """Re-exports from research/ are the actual module objects in research."""
        from heretek_swarm.research.emergent_detection import EmergentPatternDetector

        assert research.emergent_detection is not None
        assert EmergentPatternDetector is not None
        assert hasattr(research, "gwt")
        assert hasattr(research, "iit_phi")

    def test_dunder_all_contains_expected_modules(self, research) -> None:
        """__all__ lists all 14 re-exported modules."""
        expected = {
            "agency_tracking",
            "ast",
            "emergence_analyzer",
            "emergent_detection",
            "emergent_detection_types",
            "evolution_engine",
            "fep",
            "fep_active_inference",
            "gwt",
            "gwt_deliberation",
            "iit",
            "iit_phi",
            "introspection",
            "self_model",
        }
        assert set(research.__all__) == expected

    def test_research_module_has_deprecation_marker(self, research) -> None:
        """The research package docstring contains a deprecation marker."""
        assert research.__doc__ is not None
        assert "deprecated" in research.__doc__.lower()

    def test_research_readme_exists(self) -> None:
        """A README.md documents the research tier."""
        path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "backend",
            "heretek_swarm",
            "research",
            "README.md",
        )
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "research-grade" in content.lower()
        assert "Migration status" in content

    def test_legacy_imports_still_work(self) -> None:
        """Legacy class-level imports from heretek_swarm.collective still work."""
        from heretek_swarm.collective import (
            EmergenceAnalyzer,
            EmergentPatternDetector,
            EvolutionEngine,
            EmergenceLevel,
        )

        assert EmergentPatternDetector is not None
        assert EvolutionEngine is not None
        assert EmergenceAnalyzer is not None
        assert EmergenceLevel is not None

    # --- 9 new tests ---

    def test_consciousness_modules_have_expected_classes(self, research) -> None:
        """Each consciousness re-export exposes at least one class or function."""
        for name in CONSCIOUSNESS_MODULES:
            module = getattr(research, name)
            classes = [
                obj
                for _, obj in inspect.getmembers(module, inspect.isclass)
                if obj.__module__ == module.__name__
            ]
            functions = [
                obj
                for _, obj in inspect.getmembers(module, inspect.isfunction)
                if obj.__module__ == module.__name__
            ]
            assert classes or functions, (
                f"consciousness module '{name}' has no classes or functions"
            )

    def test_collective_modules_have_expected_classes(self, research) -> None:
        """Each collective re-export exposes at least one class or function."""
        for name in COLLECTIVE_MODULES:
            module = getattr(research, name)
            classes = [
                obj
                for _, obj in inspect.getmembers(module, inspect.isclass)
                if obj.__module__ == module.__name__
            ]
            functions = [
                obj
                for _, obj in inspect.getmembers(module, inspect.isfunction)
                if obj.__module__ == module.__name__
            ]
            assert classes or functions, (
                f"collective module '{name}' has no classes or functions"
            )

    def test_all_dunder_all_items_are_gettable(self, research) -> None:
        """Every name in __all__ is accessible as an attribute."""
        for name in research.__all__:
            assert hasattr(research, name), (
                f"__all__ lists '{name}' but getattr(research, '{name}') fails"
            )

    def test_all_gettable_items_are_in_dunder_all(self, research) -> None:
        """Every public non-builtin, non-stdlib attribute is listed in __all__."""
        builtins_set = set(dir(__builtins__))
        # Attributes injected by `from __future__ import annotations` or
        # other stdlib mechanisms that are not part of the research namespace.
        extra_std_attrs = {"annotations"}
        for attr in dir(research):
            if attr.startswith("_"):
                continue
            if attr in builtins_set:
                continue
            if attr in extra_std_attrs:
                continue
            assert attr in research.__all__, (
                f"public attribute '{attr}' is not in __all__"
            )

    def test_dunder_all_length_matches_export_count(self, research) -> None:
        """len(__all__) == 14 (the exact number of re-exported modules)."""
        assert len(research.__all__) == 14

    def test_consciousness_modules_are_not_empty(self, research) -> None:
        """Each consciousness module has at least 100 LOC (not stubs)."""
        for name in CONSCIOUSNESS_MODULES:
            module = getattr(research, name)
            source = inspect.getsource(module)
            loc = len(source.splitlines())
            assert loc >= 100, (
                f"consciousness module '{name}' has only {loc} LOC (expected >= 100)"
            )

    def test_collective_modules_are_not_empty(self, research) -> None:
        """Each collective module has at least 50 LOC."""
        for name in COLLECTIVE_MODULES:
            module = getattr(research, name)
            source = inspect.getsource(module)
            loc = len(source.splitlines())
            assert loc >= 50, (
                f"collective module '{name}' has only {loc} LOC (expected >= 50)"
            )

    def test_research_package_dir_contents_minimal(self, research_dir) -> None:
        """The research/ directory contains the expected moved files plus standard entries."""
        entries = set(os.listdir(research_dir))
        allowed = {
            "__init__.py",
            "__pycache__",
            "README.md",
            "emergence_analyzer.py",
            "emergent_detection.py",
            "emergent_detection_types.py",
            "evolution_engine.py",
        }
        unexpected = entries - allowed
        assert not unexpected, (
            f"Unexpected entries in research/: {unexpected}"
        )

    def test_research_package_is_deprecated(self, research) -> None:
        """The package docstring contains 'deprecated' and references M-arch PR #8."""
        doc = research.__doc__ or ""
        assert "deprecated" in doc.lower()
        assert "PR #8" in doc or "M-arch PR #8" in doc
