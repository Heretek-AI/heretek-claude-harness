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
import re
from pathlib import Path

from .base import Finding, ScannerReport, Severity

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
GITHUB_COMMIT_RE = re.compile(r"^https?://github\.com/[\w.-]+/[\w.-]+/commit/([0-9a-f]{40})/?$")


def _find_config(path: Path) -> Path | None:
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


def _block_invalid(item_id: str, rel_cfg: str, field: str, message: str) -> ScannerReport:
    """Helper: build a blocking lsp-config-invalid report."""
    return ScannerReport(
        item_id=item_id,
        scanner="config-lint",
        severity="block",
        findings=[
            Finding(
                path=f"{rel_cfg}:{field}",
                line=None,
                message=message,
                rule_id="lsp-config-invalid",
            )
        ],
    )


def _missing_config_report(item_id: str, path: Path) -> ScannerReport:
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


def _invalid_json_report(
    item_id: str, path: Path, cfg_path: Path, err: json.JSONDecodeError
) -> ScannerReport:
    return ScannerReport(
        item_id=item_id,
        scanner="config-lint",
        severity="block",
        findings=[
            Finding(
                path=str(cfg_path.relative_to(path)),
                line=None,
                message=f"LSP config invalid JSON: {err}",
                rule_id="lsp-config-invalid",
            )
        ],
    )


def _check_command(
    item_id: str, rel_cfg: str, command: object
) -> tuple[ScannerReport | None, list[Finding]]:
    """Validate cfg['command'] is a string on ALLOWLIST. Returns (block_report, findings)."""
    if not isinstance(command, str):
        block = _block_invalid(
            item_id,
            rel_cfg,
            "command",
            f"LSP 'command' must be a string, got {type(command).__name__}",
        )
        return block, []
    if command not in ALLOWLIST:
        return None, [
            Finding(
                path=f"{rel_cfg}:command",
                line=None,
                message=(
                    f"LSP command '{command}' not on allowlist (allowed: {sorted(ALLOWLIST)})"
                ),
                rule_id="lsp-command-unknown",
            )
        ]
    return None, []


def _check_urls(
    item_id: str, rel_cfg: str, cfg: dict, pinned_sha: str | None
) -> tuple[ScannerReport | None, list[Finding]]:
    """Validate cfg['rootUri'] / cfg['url'] (or skip). Returns (block_report, findings)."""
    findings: list[Finding] = []
    for url_field in ("rootUri", "url"):
        url = cfg.get(url_field)
        if url is None:
            continue
        if not isinstance(url, str):
            block = _block_invalid(
                item_id,
                rel_cfg,
                url_field,
                f"LSP '{url_field}' must be a string, got {type(url).__name__}",
            )
            return block, findings
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
    return None, findings


def _severity_from_findings(findings: list[Finding]) -> Severity:
    """Return 'block' if any blocking rule fired, else 'warn'."""
    if any(f.rule_id in ("lsp-command-unknown", "lsp-url-drift") for f in findings):
        return "block"
    return "warn"


def _compute_severity(findings: list[Finding]) -> Severity:
    return "clean" if not findings else _severity_from_findings(findings)


def scan_lsp(path: Path, *, item_id: str, pinned_sha: str | None = None) -> ScannerReport:
    """Lint the LSP config in `path`. Returns a ScannerReport."""
    findings: list[Finding] = []

    cfg_path = _find_config(path)
    if cfg_path is None:
        return _missing_config_report(item_id, path)

    try:
        cfg = json.loads(cfg_path.read_text())
    except json.JSONDecodeError as e:
        return _invalid_json_report(item_id, path, cfg_path, e)

    rel_cfg = str(cfg_path.relative_to(path))

    # D11 shape check: top-level must be a JSON object.
    if not isinstance(cfg, dict):
        return _block_invalid(
            item_id,
            rel_cfg,
            "<root>",
            f"LSP config top-level must be a JSON object, got {type(cfg).__name__}",
        )

    block, command_findings = _check_command(item_id, rel_cfg, cfg.get("command", ""))
    if block is not None:
        return block
    findings.extend(command_findings)

    block, url_findings = _check_urls(item_id, rel_cfg, cfg, pinned_sha)
    if block is not None:
        return block
    findings.extend(url_findings)

    return ScannerReport(
        item_id=item_id,
        scanner="config-lint",
        severity=_compute_severity(findings),
        findings=findings,
        raw=cfg,
    )


class LspScanner:
    def scan(self, path: Path, *, item_id: str | None = None) -> ScannerReport:
        return scan_lsp(path, item_id=item_id or path.name)
