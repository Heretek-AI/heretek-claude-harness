"""
Tests for the heretek_swarm.research namespace.

Per M-arch PR #8: verify the research tier re-exports the legacy
consciousness and collective modules so existing imports keep working
during the transition.
"""

from __future__ import annotations

import importlib


class TestResearchNamespace:
    """The research/ package re-exports the legacy modules."""

    def test_iit_phi_reexported(self) -> None:
        """heretek_swarm.research.iit_phi is the legacy module."""
        from heretek_swarm.consciousness import iit_phi as legacy
        from heretek_swarm.research import iit_phi as research

        assert research is legacy

    def test_gwt_reexported(self) -> None:
        """heretek_swarm.research.gwt is the legacy module."""
        from heretek_swarm.consciousness import gwt as legacy
        from heretek_swarm.research import gwt as research

        assert research is legacy

    def test_fep_reexported(self) -> None:
        """heretek_swarm.research.fep is the legacy module."""
        from heretek_swarm.consciousness import fep as legacy
        from heretek_swarm.research import fep as research

        assert research is legacy

    def test_emergent_detection_reexported(self) -> None:
        """heretek_swarm.research.emergent_detection is the moved module."""
        from heretek_swarm.research import emergent_detection as research

        assert research is not None
        assert hasattr(research, "EmergentPatternDetector")

    def test_evolution_engine_reexported(self) -> None:
        """heretek_swarm.research.evolution_engine is the moved module."""
        from heretek_swarm.research import evolution_engine as research

        assert research is not None
        assert hasattr(research, "EvolutionEngine")

    def test_emergence_analyzer_reexported(self) -> None:
        """heretek_swarm.research.emergence_analyzer is the moved module."""
        from heretek_swarm.research import emergence_analyzer as research

        assert research is not None
        assert hasattr(research, "EmergenceAnalyzer")

    def test_agency_tracking_reexported(self) -> None:
        """heretek_swarm.research.agency_tracking is the legacy module (stays in collective)."""
        from heretek_swarm.collective import agency_tracking as legacy
        from heretek_swarm.research import agency_tracking as research

        assert research is legacy

    def test_fep_active_inference_reexported(self) -> None:
        """heretek_swarm.research.fep_active_inference is the legacy module."""
        from heretek_swarm.consciousness import fep_active_inference as legacy
        from heretek_swarm.research import fep_active_inference as research

        assert research is legacy

    def test_self_model_reexported(self) -> None:
        """heretek_swarm.research.self_model is the legacy module."""
        from heretek_swarm.consciousness import self_model as legacy
        from heretek_swarm.research import self_model as research

        assert research is legacy

    def test_introspection_reexported(self) -> None:
        """heretek_swarm.research.introspection is the legacy module."""
        from heretek_swarm.consciousness import introspection as legacy
        from heretek_swarm.research import introspection as research

        assert research is legacy

    def test_ast_reexported(self) -> None:
        """heretek_swarm.research.ast is the legacy module."""
        from heretek_swarm.consciousness import ast as legacy
        from heretek_swarm.research import ast as research

        assert research is legacy

    def test_iit_reexported(self) -> None:
        """heretek_swarm.research.iit is the legacy module."""
        from heretek_swarm.consciousness import iit as legacy
        from heretek_swarm.research import iit as research

        assert research is legacy

    def test_gwt_deliberation_reexported(self) -> None:
        """heretek_swarm.research.gwt_deliberation is the legacy module."""
        from heretek_swarm.consciousness import gwt_deliberation as legacy
        from heretek_swarm.research import gwt_deliberation as research

        assert research is legacy

    def test_emergent_detection_types_reexported(self) -> None:
        """heretek_swarm.research.emergent_detection_types is the moved module."""
        from heretek_swarm.research import emergent_detection_types as research

        assert research is not None
        assert hasattr(research, "EmergenceLevel")

    def test_all_attribute_complete(self) -> None:
        """__all__ is non-empty and contains string identifiers."""
        research = importlib.import_module("heretek_swarm.research")
        assert isinstance(research.__all__, list)
        assert len(research.__all__) > 0
        for name in research.__all__:
            assert isinstance(name, str)

    def test_all_attributes_resolve(self) -> None:
        """Every name in __all__ resolves to an actual attribute."""
        research = importlib.import_module("heretek_swarm.research")
        for name in research.__all__:
            assert hasattr(research, name), f"Missing: {name}"
