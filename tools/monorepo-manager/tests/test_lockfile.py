"""Tests for the lockfile hashing utility."""

from __future__ import annotations

from scripts.lib.lockfile import compute_lockfile_hash, verify_lockfile


def test_compute_lockfile_hash_is_hex_and_stable():
    h1 = compute_lockfile_hash()
    h2 = compute_lockfile_hash()
    assert h1 == h2
    assert len(h1) == 64
    int(h1, 16)


def test_verify_lockfile_passes_with_current_hash():
    h = compute_lockfile_hash()
    assert verify_lockfile(h) is True


def test_verify_lockfile_fails_with_wrong_hash():
    assert verify_lockfile("0" * 64) is False
