"""Tests for system prompts."""

from tier1.llm.prompts import SYSTEM_PROMPTS


def test_all_four_agents_have_prompts():
    assert set(SYSTEM_PROMPTS.keys()) == {"steward", "alpha", "beta", "charlie"}


def test_alpha_prompt_mentions_analysis_role():
    p = SYSTEM_PROMPTS["alpha"].lower()
    assert "alpha" in p
    assert "analysis" in p or "deconstruct" in p


def test_beta_prompt_mentions_validation_role():
    p = SYSTEM_PROMPTS["beta"].lower()
    assert "beta" in p
    assert "validat" in p or "reality" in p


def test_charlie_prompt_mentions_challenge_role():
    p = SYSTEM_PROMPTS["charlie"].lower()
    assert "charlie" in p
    assert "challenge" in p or "adversarial" in p


def test_prompts_specify_json_output():
    for agent in ("alpha", "beta", "charlie"):
        p = SYSTEM_PROMPTS[agent].lower()
        assert "json" in p, f"{agent} prompt missing json spec"
        assert "position" in p, f"{agent} prompt missing 'position'"
        assert "confidence" in p, f"{agent} prompt missing 'confidence'"
        assert "reasoning" in p, f"{agent} prompt missing 'reasoning'"


def test_prompts_non_empty():
    for agent, prompt in SYSTEM_PROMPTS.items():
        assert prompt.strip(), f"{agent} prompt is empty"
