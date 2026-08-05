"""LSP config linter. Heretek-owned; no third-party binary.

The LSP entries in catalog.yaml are JSON pointers to user-installed
binaries. There is no code-execution surface to scan, but the *config*
itself can drift — pointing at a wrong commit URL, or a command name
not on our allowlist.

Checks:
  - .lsp.json (or .lsp/<name>.json) exists in the item directory.
  - `command` field is on the ALLOWLIST.
  - `rootUri` / `url` (if present) is a github commit URL whose 40-char
    SHA matches the catalog entry's pinned sha (caller passes pinned_sha).

If pinned_sha is None, the SHA-match check is skipped (catalog doesn't
carry it for LSPs today; TODO if we add a sha field for LSPs in v2).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from .base import Finding, ScannerReport, Severity

log = logging.getLogger(__name__)

# Allowlist of LSP server binary names. Anything else is a block.
# Extend with care: each new entry needs to be vetted per D7.
ALLOWLIST = frozenset(
    {
        "rust-analyzer",
        "basedpyright",
        "pyright",
        "biome",
        "oxc",
        "gopls",
        "clangd",
        "typescript-language-server",
        "vue-language-server",
        "solargraph",
    }
)

# github commit URL pattern
GITHUB_COMMIT_RE = re.compile(
    r"^https?://github\.com/[\w.-]+/[\w.-]+/commit/([0-9a-f]{40})/?$"
)


def _find_config(path: Path) -> Optional[Path]:
    """Find the LSP config JSON inside `path`."""
    candidates = [path / ".lsp.json", path / "lsp.json"]
    for c in candidates:
        if c.exists():
            return c
    # also allow .lsp/<name>.json
    lsp_dir = path / ".lsp"
    if lsp_dir.is_dir():
        for f in lsp_dir.glob("*.json"):
            return f
    return None


def scan_lsp(
    path: Path, *, item_id: str, pinned_sha: Optional[str] = None
) -> ScannerReport:
    """Lint the LSP config in `path`. Returns a ScannerReport."""
    findings: list[Finding] = []

    cfg_path = _find_config(path)
    if cfg_path is None:
        return ScannerReport(
            item_id=item_id,
            scanner="config-lint",
            severity="warn",
            findings=[
                Finding(
                    path=str(path),
                    line=None,
                    message="LSP config (.lsp.json or lsp.json) missing",
                    rule_id="lsp-config-missing",
                )
            ],
        )

    try:
        cfg = json.loads(cfg_path.read_text())
    except json.JSONDecodeError as e:
        return ScannerReport(
            item_id=item_id,
            scanner="config-lint",
            severity="block",
            findings=[
                Finding(
                    path=str(cfg_path.relative_to(path)),
                    line=None,
                    message=f"LSP config invalid JSON: {e}",
                    rule_id="lsp-config-invalid",
                )
            ],
        )

    rel_cfg = str(cfg_path.relative_to(path))
    command = cfg.get("command", "")
    if command not in ALLOWLIST:
        findings.append(
            Finding(
                path=f"{rel_cfg}:command",
                line=None,
                message=(
                    f"LSP command '{command}' not on allowlist "
                    f"(allowed: {sorted(ALLOWLIST)})"
                ),
                rule_id="lsp-command-unknown",
            )
        )

    # If a rootUri is a github commit URL, check it matches the pinned sha
    for url_field in ("rootUri", "url"):
        url = cfg.get(url_field)
        if not url:
            continue
        m = GITHUB_COMMIT_RE.match(url)
        if m and pinned_sha and m.group(1) != pinned_sha:
            findings.append(
                Finding(
                    path=f"{rel_cfg}:{url_field}",
                    line=None,
                    message=(
                        f"{url_field} points at commit {m.group(1)[:12]}… "
                        f"but catalog pins {pinned_sha[:12]}…"
                    ),
                    rule_id="lsp-url-drift",
                )
            )

    severity: Severity = "clean" if not findings else (
        "block" if any(f.rule_id in ("lsp-command-unknown", "lsp-url-drift") for f in findings)
        else "warn"
    )

    return ScannerReport(
        item_id=item_id,
        scanner="config-lint",
        severity=severity,
        findings=findings,
        raw=cfg,
    )


class LspScanner:
    def scan(self, path: Path, *, item_id: str | None = None) -> ScannerReport:
        return scan_lsp(path, item_id=item_id or path.name)