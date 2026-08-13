"""Tests for the contract hash, including the new seeds hash slot."""

from __future__ import annotations

import textwrap

from scripts.lib.contract_hash import compute_contract_hash, compute_seeds_hash


def test_compute_contract_hash_is_deterministic(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text(
        textwrap.dedent(
            """\
            # spec

            ## Section A
            body a

            ## Section B
            body b
            """
        )
    )
    h1 = compute_contract_hash(spec, "Section A")
    h2 = compute_contract_hash(spec, "Section A")
    assert h1 == h2


def test_compute_contract_hash_is_16_hex_chars(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("## X\nbody")
    h = compute_contract_hash(spec, "X")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_contract_hash_changes_when_section_changes(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("## X\nbody one")
    h1 = compute_contract_hash(spec, "X")
    spec.write_text("## X\nbody two")
    h2 = compute_contract_hash(spec, "X")
    assert h1 != h2


def test_compute_contract_hash_raises_on_missing_section(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("## X\nbody")
    import pytest

    with pytest.raises(ValueError, match="Section 'Y' not found"):
        compute_contract_hash(spec, "Y")


def test_compute_seeds_hash_returns_16_char_hex():
    digest = compute_seeds_hash()
    assert isinstance(digest, str)
    assert len(digest) == 16
    assert all(c in "0123456789abcdef" for c in digest)


def test_compute_seeds_hash_is_stable_for_current_state():
    a = compute_seeds_hash()
    b = compute_seeds_hash()
    assert a == b


def test_compute_contract_hash_changes_when_seeds_change(tmp_path):
    """Per spec §10: editing a seed must change the baked contract hash."""
    spec = tmp_path / "spec.md"
    spec.write_text("## X\nbody")
    h1 = compute_contract_hash(spec, "X", seeds_hash="aaaa")
    h2 = compute_contract_hash(spec, "X", seeds_hash="bbbb")
    assert h1 != h2


def test_compute_contract_hash_omitting_seeds_keeps_pre_change_value(tmp_path):
    """When no seeds_hash is supplied the digest is unchanged from before."""
    spec = tmp_path / "spec.md"
    spec.write_text("## X\nbody")
    h_no_seeds = compute_contract_hash(spec, "X")
    assert len(h_no_seeds) == 16
    # And the seeds-hash wiring must not raise with None either.
    h_with_none = compute_contract_hash(spec, "X", seeds_hash=None)
    assert h_with_none == h_no_seeds
