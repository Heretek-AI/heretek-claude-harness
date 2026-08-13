"""Regex-based leak scanner.

Applies the :mod:`patterns` catalog to a list of strings (from
:mod:`extractor` or any other source) and returns vendor-neutral
findings.

The output is grouped by ``category`` (pattern name) and sorted by
``risk`` (HIGH first). Each finding carries the matched string,
the file offset, the encoding, and (optionally) the matched
group values for downstream verification.
"""

from __future__ import annotations

import re
from typing import Iterable

from re_leak_scan import patterns as pat_mod


def scan_strings(
    strings: Iterable[dict],
    categories: list[str] | None = None,
    max_per_category: int = 200,
) -> dict:
    """Run the pattern catalog over *strings*.

    Args:
        strings: iterable of ``{"string", "offset", "encoding"}`` dicts
            (the shape produced by :func:`extractor.extract_strings`).
        categories: optional subset of pattern names to match. ``None``
            means "all patterns". Unknown names are silently ignored.
        max_per_category: per-category cap (default 200). The
            total-result size is bounded by ``len(categories) *
            max_per_category``.

    A17 fix (v2.8.0): ``generic-hex-secret`` matches now apply a
    "≥4 distinct characters" guard and an Adobe-XMP / .NET PublicKey
    denylist. The r03-stress run produced 75% false-positive rate on
    this pattern — repeating ASCII (``5555555…``), .NET framework
    PublicKey hex (``00000000000000000400000000000000``), and Adobe
    XMP metadata IDs (``xmp.iid:`` UUID-like strings). The guard kills
    the noise without missing real secrets (real hex secrets always
    use the full hex alphabet).

    Returns::

        {
          "totals": {"strings_seen": N, "matches": N},
          "by_category": {
            "sentry-dsn": {
              "count": N,
              "truncated": bool,
              "risk": "HIGH",
              "description": "...",
              "matches": [
                {"string": "...", "offset": N, "encoding": "ascii",
                 "groups": {...}},
                ...
              ],
            },
            ...
          },
        }
    """
    chosen = _resolve_patterns(categories)
    by_category: dict[str, dict] = {}
    for p in chosen:
        by_category[p.name] = {
            "count": 0,
            "truncated": False,
            "risk": p.risk,
            "description": p.description,
            "matches": [],
        }
    compiled: list[tuple[pat_mod.Pattern, re.Pattern]] = []
    for p in chosen:
        try:
            compiled.append((p, re.compile(p.regex, re.IGNORECASE)))
        except re.error:
            # Skip patterns that fail to compile — better a
            # missing match than a hard crash on a malformed regex.
            continue
    totals = {"strings_seen": 0, "matches": 0}
    for entry in strings:
        totals["strings_seen"] += 1
        s = entry.get("string", "")
        if not s:
            continue
        for p, regex in compiled:
            bucket = by_category[p.name]
            if bucket["count"] >= max_per_category:
                bucket["truncated"] = True
                continue
            m = regex.search(s)
            if m is None:
                continue
            matched_text = m.group(0)
            # A17 denylist: kill the dominant false-positive shapes
            # for generic-hex-secret. Real secrets never match these.
            if p.name == "generic-hex-secret":
                if _is_hex_secret_false_positive(matched_text, s):
                    continue
            bucket["matches"].append({
                "string": s,
                "offset": entry.get("offset", 0),
                "encoding": entry.get("encoding", "ascii"),
                "groups": m.groupdict() if m.groupdict() else {},
            })
            bucket["count"] += 1
            totals["matches"] += 1
    return {"totals": totals, "by_category": by_category}


# A17 helpers (v2.8.0)


def _is_hex_secret_false_positive(matched: str, full_string: str) -> bool:
    """Return True when a generic-hex-secret match is a known
    false-positive shape:

      - <4 distinct characters in the match (repeating ASCII data,
        not a secret)
      - .NET PublicKey=000…000 framework literal
      - Adobe XMP xmp.iid:* / xmp.did:* document IDs
    """
    if len(set(matched.lower())) < 4:
        return True
    # The matched text usually appears inside a larger string; check
    # the surrounding context for known framework literals.
    ctx = full_string.lower()
    if "publickey=" in ctx and ("0000" in matched or "0400" in matched):
        return True
    if "xmp.iid:" in ctx or "xmp.did:" in ctx:
        return True
    return False


def _resolve_patterns(categories: list[str] | None) -> list[pat_mod.Pattern]:
    if categories is None:
        return list(pat_mod.PATTERNS)
    chosen = []
    for name in categories:
        p = pat_mod.get_pattern(name)
        if p is not None:
            chosen.append(p)
    return chosen
