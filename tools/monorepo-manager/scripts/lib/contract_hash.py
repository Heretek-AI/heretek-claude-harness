"""Spec contract hashing.

The init-harness.sh script bakes a hash of the relevant spec section into
every generated reference install. On subsequent inits, recomputing the
hash and comparing against the baked value detects drift.
"""

from __future__ import annotations

import hashlib
import pathlib
import re
from pathlib import Path


def _extract_section(spec_text: str, section_anchor: str) -> str:
    """Extract a markdown section by anchor (e.g. 'Section A' or '4. Layer 1').

    Returns the section body from the anchor line through the next
    '## ' or '### ' heading at the same or higher level. Raises
    ValueError if the anchor is not found.
    """
    lines = spec_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^#+\s+.*\b{re.escape(section_anchor)}\b", line):
            start = i
            break
    if start is None:
        raise ValueError(f"Section '{section_anchor}' not found in spec")

    # Capture everything until the next heading at the same level or higher.
    start_level = len(lines[start]) - len(lines[start].lstrip("#"))
    body_lines: list[str] = []
    for line in lines[start + 1 :]:
        leading = len(line) - len(line.lstrip("#")) if line.lstrip().startswith("#") else 999
        if line.strip() and leading <= start_level:
            break
        body_lines.append(line)
    return "\n".join([lines[start], *body_lines]).strip()


def compute_contract_hash(
    spec_path: pathlib.Path,
    section_anchor: str,
    seeds_hash: str | None = None,
) -> str:
    """Return a 16-char hex SHA-256 prefix over the spec section text.

    When ``seeds_hash`` is provided, it is incorporated into the digest so
    that editing a ``seeds/*.yaml`` file changes the contract hash (per
    spec §10: drift detection must flag seed edits).
    """
    text = pathlib.Path(spec_path).read_text(encoding="utf-8")
    section = _extract_section(text, section_anchor)
    h = hashlib.sha256(section.encode("utf-8"))
    if seeds_hash:
        h.update(b"\0seeds:")
        h.update(seeds_hash.encode("utf-8"))
    return h.hexdigest()[:16]


def compute_seeds_hash() -> str:
    """Return a 16-char hex SHA-256 prefix over the three seeds/*.yaml files.

    The hash is computed over the on-disk rendered files (the canonical
    source). Ordering is alphabetical by filename for determinism.
    """
    seeds_dir = Path(__file__).parents[2] / "seeds"
    files = sorted(seeds_dir.glob("*.yaml"))
    h = hashlib.sha256()
    for path in files:
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:16]
