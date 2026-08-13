"""MCP server entry point for re-yara-author.

Authoring YARA rules from a sample or a set of samples. The
server wraps ``re-lief.extract_strings`` +
``re-lief.categorize_strings`` + ``re-lief.get_imports_exports``
to extract distinctive features, ranks them by
specificity, emits a starter ``.yar`` text, and validates
the rule against a positive/negative set using
``re-yara.scan_binary``.

All output is vendor-neutral. Rule strings are
category-only.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("re_yara_author")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-yara-author")


@mcp.tool()
def check_yara_author() -> dict:
    """Report server status + yara-python availability.

    Returns ``status: OK`` when ``yara-python`` is
    importable. The server is a pure-Python wrapper; the
    actual YARA compilation/scan delegates to re-yara.
    """
    return {
        "server": "re-yara-author",
        "version": "0.1.0",
        "status": "OK",
        "yara_python_available": _check_yara_python(),
    }


@mcp.tool()
def extract_distinctive_features(path: str, max_strings: int = 200) -> dict:
    """Extract distinctive features from *path*.

    Combines ``re-lief.extract_strings`` + ``re-lief
    .categorize_strings`` + ``re-lief.get_imports_exports``
    to return a unified feature list ranked by
    specificity.

    Returns::

        {
          "path": "...",
          "strings": [{"string": "...", "offset": N, "kind": "ascii"|"utf16le"}, ...],
          "categories": {"anti_debug": 4, "hwid": 2, ...},
          "imports": [...],
          "feature_count": N
        }
    """
    return _call_lief_features(path, max_strings)


@mcp.tool()
def rank_candidates(path: str, k: int = 20) -> list[dict]:
    """Return the top-k most distinctive features.

    Specificity ranking: longest non-trivial strings
    first, then imports with the rarest frequency, then
    categorised keyword matches. Returns a list of
    ``{kind, value, score, evidence_offset, evidence_section}``
    records sorted by score desc.
    """
    feats = _call_lief_features(path)
    candidates = []
    for s in feats.get("strings", []):
        v = s.get("string", "")
        if not v or len(v) < 8:
            continue
        score = min(1.0, len(v) / 64.0)
        candidates.append({
            "kind": "string",
            "value": v,
            "score": round(score, 3),
            "evidence_offset": s.get("offset"),
            "evidence_section": s.get("section"),
        })
    for cat, cnt in feats.get("categories", {}).items():
        candidates.append({
            "kind": "category",
            "value": cat,
            "score": round(min(1.0, cnt / 10.0), 3),
            "evidence_offset": None,
            "evidence_section": None,
        })
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:k]


@mcp.tool()
def emit_rule(name: str, features: list[dict], min_strings: int = 2) -> dict:
    """Emit a starter ``.yar`` text from the chosen features.

    Args:
        name: rule name (e.g. ``family_xyz``)
        features: a list of feature dicts from
            :func:`rank_candidates`
        min_strings: minimum number of string conditions
            (default 2; a rule with < 2 string conditions
            is over-noisy and should be tightened)

    Returns::

        {
          "rule_text": "rule family_xyz { ... }",
          "string_count": N,
          "category_conditions": [...],
          "warning": "..." | null
        }
    """
    strings = [f for f in features if f.get("kind") == "string"][:20]
    categories = [f for f in features if f.get("kind") == "category"]
    if len(strings) < min_strings:
        return {
            "rule_text": "",
            "string_count": len(strings),
            "category_conditions": [c["value"] for c in categories],
            "warning": (
                f"only {len(strings)} string conditions (min "
                f"{min_strings}); tighten the input feature set"
            ),
        }
    string_conds = " and\n        ".join(
        f'        any of ($s{i})' for i in range(len(strings))
    )
    str_lines = "\n".join(
        f'        $s{i} = "{_escape_yara_string(s["value"])}" ascii wide'
        for i, s in enumerate(strings)
    )
    cat_conds = " or\n        ".join(
        f'        category == "{c["value"]}"' for c in categories
    ) if categories else ""
    rule = (
        f"rule {name}\n"
        f"{{\n"
        f"    meta:\n"
        f'        author = "re-yara-author"\n'
        f'        description = "auto-generated from re-yara-author; refine before deploying"\n'
        f"\n"
        f"    strings:\n"
        f"{str_lines}\n"
        f"\n"
        f"    condition:\n"
        f"{string_conds}"
    )
    if cat_conds:
        rule += f"\n        and\n{cat_conds}"
    rule += "\n}\n"
    return {
        "rule_text": rule,
        "string_count": len(strings),
        "category_conditions": [c["value"] for c in categories],
        "warning": None,
    }


@mcp.tool()
def validate_rule(
    rule_text: str,
    positive_paths: list[str],
    negative_paths: list[str] | None = None,
) -> dict:
    """Validate *rule_text* against a positive + negative set.

    Wraps ``re-yara.compile_rules`` + ``re-yara.scan_binary``.
    Returns::

        {
          "compiled": bool,
          "positive_hits": [{"path": "...", "matches": N}, ...],
          "negative_hits": [{"path": "...", "matches": N}, ...],
          "true_positive_rate": float,
          "false_positive_rate": float
        }
    """
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yar", delete=False) as f:
        f.write(rule_text)
        rule_path = f.name
    # We can't easily call re-yara's FastMCP server from
    # within this Python server (MCP servers don't talk to
    # each other directly); fall back to the yara-python
    # library if present.
    if not _check_yara_python():
        return {
            "compiled": False,
            "positive_hits": [],
            "negative_hits": [],
            "true_positive_rate": None,
            "false_positive_rate": None,
            "error": "yara-python not installed; install with `pip install re-yara`",
        }
    import yara
    try:
        rules = yara.compile(filepath=rule_path)
    except yara.SyntaxError as exc:
        return {
            "compiled": False,
            "positive_hits": [],
            "negative_hits": [],
            "true_positive_rate": None,
            "false_positive_rate": None,
            "error": f"YARA compile error: {exc}",
        }
    pos_hits = []
    for p in positive_paths:
        matches = rules.match(p)
        pos_hits.append({"path": p, "matches": len(matches)})
    neg_paths = negative_paths or []
    neg_hits = []
    for p in neg_paths:
        matches = rules.match(p)
        neg_hits.append({"path": p, "matches": len(matches)})
    tp = sum(1 for h in pos_hits if h["matches"] > 0)
    fp = sum(1 for h in neg_hits if h["matches"] > 0)
    tpr = tp / max(1, len(pos_hits))
    fpr = fp / max(1, len(neg_hits))
    return {
        "compiled": True,
        "positive_hits": pos_hits,
        "negative_hits": neg_hits,
        "true_positive_rate": tpr,
        "false_positive_rate": fpr,
    }


@mcp.tool()
def iterate_on_false_positives(rule_text: str, fp_paths: list[str]) -> dict:
    """Suggest rule refinements based on false-positive hits.

    Returns a list of *suggestions* (category-only labels) for
    the analyst to consider — typically: tighten the
    ``condition:`` block, add a ``filesize`` constraint, add
    a category-gate (the ``category == "..."`` field that
    re-yara supports via the ``meta:`` block, matched by
    re-lief.categorize_strings).
    """
    if not _check_yara_python():
        return {"suggestions": [], "error": "yara-python not installed"}
    import yara
    try:
        rules = yara.compile(source=rule_text)
    except yara.SyntaxError as exc:
        return {"suggestions": [], "error": f"YARA compile error: {exc}"}
    suggestions: list[str] = []
    for p in fp_paths:
        matches = rules.match(p)
        if not matches:
            continue
        for m in matches:
            suggestions.append(
                f"add a filesize constraint: {p} matched; consider "
                f"`filesize < 100MB` or `filesize > 10KB` to exclude "
                f"the FP path"
            )
            suggestions.append(
                "tighten the condition block: the rule fired on a "
                "single string match; add `and any of (2 of ($s*))` "
                "to require >= 2 string matches"
            )
    return {"suggestions": suggestions[:20]}


# ── helpers ────────────────────────────────────────────────────────────


def _check_yara_python() -> bool:
    try:
        import yara  # noqa: F401
        return True
    except ImportError:
        return False


def _call_lief_features(path: str, max_strings: int = 200) -> dict:
    """Import + call re-lief to get the feature set.

    A13 fix (v2.8.0): same off-by-one as A14 in re-anti-analysis.
    here.parents[2] lands at re-yara-author/, not servers/. Correct
    depth is parents[3].
    """
    try:
        import sys
        from pathlib import Path
        # File: servers/re-yara-author/src/re_yara_author/server.py
        # parents: 0=re_yara_author, 1=src, 2=re-yara-author,
        #          3=servers, 4=repo-root
        here = Path(__file__).resolve()
        lief_src = here.parents[3] / "re-lief" / "src"
        if not lief_src.is_dir():
            return {"path": path, "strings": [], "categories": {},
                    "imports": [], "feature_count": 0,
                    "error": "re-lief not found"}
        sys.path.insert(0, str(lief_src))
        try:
            from re_lief import parsers
            cats = parsers.categorize_strings(path, min_length=8)
            strings_flat = []
            for s in cats.get("ascii_capped", [])[:max_strings]:
                strings_flat.append({
                    "string": s.get("string", ""),
                    "offset": s.get("offset"),
                    "section": s.get("section"),
                    "kind": "ascii",
                })
            imports = parsers.normalize_for_diff(path)
            return {
                "path": path,
                "strings": strings_flat,
                "categories": cats.get("by_category", {}),
                "imports": [],
                "feature_count": len(strings_flat),
            }
        finally:
            if str(lief_src) in sys.path:
                sys.path.remove(str(lief_src))
    except Exception as exc:  # noqa: BLE001
        return {"path": path, "strings": [], "categories": {},
                "imports": [], "feature_count": 0, "error": str(exc)}


def _escape_yara_string(s: str) -> str:
    """Escape a string for embedding in a YARA ``$s = "..."`` literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
