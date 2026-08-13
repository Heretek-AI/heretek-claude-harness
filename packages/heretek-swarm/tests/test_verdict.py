"""Tests for consensus/verdict.py — structured tribunal ruling (G-02)."""

from heretek_swarm_core.consensus.verdict import (
    RulingVerdict,
    aggregate_triad_ruling,
    keyword_fallback_verdict,
    parse_agent_verdict,
)
import pydantic
import pytest


class TestParseAgentVerdict:
    def test_valid_json_extracted(self):
        r = parse_agent_verdict('{"verdict": "emergent", "confidence": 0.9}')
        assert r is not None
        assert r.verdict == "emergent"
        assert r.confidence == 0.9

    def test_fenced_json_in_markdown(self):
        r = parse_agent_verdict('```json\n{"verdict": "threat", "confidence": 0.8}\n```')
        assert r is not None
        assert r.verdict == "threat"

    def test_invalid_json_returns_none(self):
        assert parse_agent_verdict("not json") is None
        assert parse_agent_verdict("") is None
        assert parse_agent_verdict(None) is None  # type: ignore[arg-type]


class TestKeywordFallbackVerdict:
    def test_threat_keywords(self):
        r = keyword_fallback_verdict("This is a critical threat")
        assert r.verdict == "threat"
        assert r.confidence == 0.5

    def test_emergent_keywords(self):
        r = keyword_fallback_verdict("Novel beneficial breakthrough pattern")
        assert r.verdict == "emergent"
        assert r.confidence == 0.5

    def test_inconclusive_no_match(self):
        r = keyword_fallback_verdict("Everything looks normal")
        assert r.verdict == "inconclusive"
        assert r.confidence == 0.5


class TestAggregateTriadRuling:
    def test_all_structured_emergent(self):
        r = aggregate_triad_ruling(
            '{"verdict": "emergent", "confidence": 0.9}',
            '{"verdict": "emergent", "confidence": 0.85}',
            '{"verdict": "emergent", "confidence": 0.95}',
        )
        assert r.verdict == "emergent"
        assert r.confidence > 0.8

    def test_majority_threat_wins(self):
        r = aggregate_triad_ruling(
            '{"verdict": "threat", "confidence": 0.9}',
            '{"verdict": "emergent", "confidence": 0.5}',
            '{"verdict": "threat", "confidence": 0.95}',
        )
        assert r.verdict == "threat"

    def test_all_keyword_fallback(self):
        r = aggregate_triad_ruling(
            "Immediate threat detected",
            "Critical danger",
            "Malicious code found",
        )
        assert r.verdict == "threat"

    def test_empty_inputs_inconclusive(self):
        r = aggregate_triad_ruling("", "", "")
        assert r.verdict == "inconclusive"


class TestRulingVerdictSchema:
    def test_rejects_invalid_verdict_label(self):
        with pytest.raises(pydantic.ValidationError):
            RulingVerdict(verdict="maybe", confidence=0.5)  # type: ignore[arg-type]

    def test_rejects_out_of_range_confidence(self):
        with pytest.raises(pydantic.ValidationError):
            RulingVerdict(verdict="emergent", confidence=1.5)
