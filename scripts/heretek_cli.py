"""heretek CLI — top-level package management & distribution CLI for heretek marketplace.

Provides end-user subcommands for repository auto-detection (`init`), plugin package
installation (`install`), terminal quality scorecards (`status`), fast-gate SLA benchmarks (`metrics`),
schema validation (`validate`), catalog building (`build-catalog`), and telemetry log inspection (`telemetry`).

Top-level CLI execution entry:
    `npx heretek <command> [args]` or `python scripts/heretek_cli.py <command> [args]`
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

# Resolve repository root directory and append to sys.path for internal imports
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_marketplace import generate as generate_marketplace
from scripts.validate import validate_all

# Directory constants
PLUGINS_DIR = REPO_ROOT / "plugins"
TELEMETRY_ROOT = Path(
    os.environ.get("HERETEK_TELEMETRY_ROOT", Path.home() / ".heretek" / "telemetry")
)
SCHEMA_PATH = REPO_ROOT / "tests" / "fixtures" / "telemetry_schema.json"


def cmd_install(args: argparse.Namespace) -> int:
    """Install a plugin package bundle into a target project directory.

    Args:
        args: Parsed CLI namespace containing `pack_name` (str) and `target` (str path).

    Returns:
        0 on clean installation pass, 1 if plugin source directory does not exist.
    """
    pack_name: str = args.pack_name
    target_dir = Path(args.target).resolve()
    plugin_src = PLUGINS_DIR / pack_name

    if not plugin_src.is_dir():
        print(f"error: plugin pack '{pack_name}' not found in plugins/", file=sys.stderr)
        return 1

    claude_dir = target_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    installed_files: list[str] = []

    # 1. Manifests under .claude-plugin/ (plugin.json, etc.)
    manifest_src = plugin_src / ".claude-plugin"
    if manifest_src.is_dir():
        plugin_dest = claude_dir / "plugins" / pack_name
        plugin_dest.mkdir(parents=True, exist_ok=True)
        for item in manifest_src.iterdir():
            if item.is_file():
                dest = plugin_dest / item.name
                shutil.copy2(item, dest)
                installed_files.append(str(dest.relative_to(target_dir)))

    # 2. LSP configuration (.lsp.json -> .claude/lsp.json)
    lsp_src = plugin_src / ".lsp.json"
    if lsp_src.is_file():
        lsp_dest = claude_dir / "lsp.json"
        shutil.copy2(lsp_src, lsp_dest)
        installed_files.append(str(lsp_dest.relative_to(target_dir)))

    # 3. MCP configuration (.mcp.json -> .mcp.json and .claude/mcp.json)
    mcp_src = plugin_src / ".mcp.json"
    if mcp_src.is_file():
        mcp_dest_root = target_dir / ".mcp.json"
        mcp_dest_claude = claude_dir / "mcp.json"
        shutil.copy2(mcp_src, mcp_dest_root)
        shutil.copy2(mcp_src, mcp_dest_claude)
        installed_files.append(str(mcp_dest_root.relative_to(target_dir)))
        installed_files.append(str(mcp_dest_claude.relative_to(target_dir)))

    # 4. Hooks configuration & scripts (hooks.json -> .claude/hooks.json)
    hooks_src = plugin_src / "hooks.json"
    if not hooks_src.is_file():
        for alt in (plugin_src / "hooks" / "hooks.json", plugin_src / ".claude-plugin" / "hooks.json"):
            if alt.is_file():
                hooks_src = alt
                break

    if hooks_src.is_file():
        hooks_dest = claude_dir / "hooks.json"
        shutil.copy2(hooks_src, hooks_dest)
        installed_files.append(str(hooks_dest.relative_to(target_dir)))

    # Copy associated interceptor scripts into .claude/scripts/
    scripts_src = plugin_src / "scripts"
    if scripts_src.is_dir():
        scripts_dest = claude_dir / "scripts"
        scripts_dest.mkdir(parents=True, exist_ok=True)
        for script_file in scripts_src.rglob("*"):
            if script_file.is_file() and "__pycache__" not in script_file.parts:
                rel = script_file.relative_to(scripts_src)
                dest = scripts_dest / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(script_file, dest)
                installed_files.append(str(dest.relative_to(target_dir)))

    # 5. Skills directory (skills/ -> .claude/skills/)
    skills_src = plugin_src / "skills"
    if skills_src.is_dir():
        skills_dest = claude_dir / "skills"
        skills_dest.mkdir(parents=True, exist_ok=True)
        for skill_file in skills_src.rglob("*"):
            if skill_file.is_file():
                rel = skill_file.relative_to(skills_src)
                dest = skills_dest / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(skill_file, dest)
                installed_files.append(str(dest.relative_to(target_dir)))

    # 6. Pre-commit configuration (.pre-commit-config.yaml -> .pre-commit-config.yaml)
    precommit_src = plugin_src / ".pre-commit-config.yaml"
    if precommit_src.is_file():
        precommit_dest = target_dir / ".pre-commit-config.yaml"
        shutil.copy2(precommit_src, precommit_dest)
        installed_files.append(str(precommit_dest.relative_to(target_dir)))

    print(f"Successfully installed '{pack_name}' into {target_dir}")
    print(f"Deployed {len(installed_files)} asset file(s):")
    for path_str in sorted(installed_files):
        print(f"  - {path_str}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate all plugin manifests and marketplace.json against JSON Schemas.

    Args:
        args: Parsed CLI namespace containing optional `repo_root` and `schemas_dir`.

    Returns:
        0 on validation pass, 1 if schema validation errors are detected.
    """
    repo_root = Path(args.repo_root).resolve() if getattr(args, "repo_root", None) else REPO_ROOT
    schemas_dir = (
        Path(args.schemas_dir).resolve()
        if getattr(args, "schemas_dir", None)
        else REPO_ROOT / "tests" / "schemas"
    )
    errors = validate_all(repo_root, schemas_dir=schemas_dir)
    if not errors:
        print("validate: OK (all manifests conform to JSON Schemas)")
        return 0
    print(f"validate: {len(errors)} error(s)", file=sys.stderr)
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    return 1


def cmd_build_catalog(args: argparse.Namespace) -> int:
    """Build canonical .claude-plugin/marketplace.json from catalog/catalog.yaml.

    Args:
        args: Parsed CLI namespace containing optional `catalog` and `output` paths.

    Returns:
        0 on successful generation, 1 on failure.
    """
    catalog_path = (
        Path(args.catalog).resolve()
        if getattr(args, "catalog", None)
        else REPO_ROOT / "catalog" / "catalog.yaml"
    )
    output_path = (
        Path(args.output).resolve()
        if getattr(args, "output", None)
        else REPO_ROOT / ".claude-plugin" / "marketplace.json"
    )
    try:
        generate_marketplace(catalog_path, output_path)
    except Exception as exc:
        print(f"build-catalog: error: {exc}", file=sys.stderr)
        return 1
    print(f"build-catalog: wrote {output_path}")
    return 0


def _iter_session_files(root: Path) -> list[Path]:
    """Iterate through session JSONL files under TELEMETRY_ROOT."""
    sessions_dir = root / "sessions"
    if not sessions_dir.exists():
        return []
    return sorted(sessions_dir.glob("*/*.jsonl"))


def _read_events(files: list[Path]) -> list[dict[str, object]]:
    """Read and parse telemetry event dicts from JSONL files."""
    events: list[dict[str, object]] = []
    dropped = 0
    for f in files:
        for line in f.read_text().splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            try:
                parsed: object = json.loads(line_str)
                if isinstance(parsed, dict):
                    events.append(parsed)  # type: ignore[arg-type]
            except json.JSONDecodeError:
                dropped += 1
                continue
    if dropped:
        print(f"warning: {dropped} malformed JSONL line(s) skipped", file=sys.stderr)
    return events


def cmd_telemetry_show(args: argparse.Namespace) -> int:
    """Display logged telemetry hook events matching criteria."""
    files = _iter_session_files(TELEMETRY_ROOT)
    session_arg: str | None = args.session
    if session_arg:
        files = [f for f in files if session_arg in f.name]
    events = _read_events(files)
    tool_arg: str | None = args.tool
    if tool_arg:
        events = [e for e in events if e.get("tool_name") == tool_arg]
    since_arg: str | None = args.since
    if since_arg:
        events = [e for e in events if str(e.get("ts", "")) >= since_arg]
    if not events:
        print("(no events)", file=sys.stderr)
        return 0
    for e in events:
        ts = str(e.get("ts", "?"))
        event_type = str(e.get("event_type", "?"))
        tool_name = str(e.get("tool_name", "?"))
        decision = str(e.get("hook_decision", "?"))
        input_path = str(e.get("tool_input_path", ""))
        print(f"{ts:<27} {event_type:<11} {tool_name:<10} {decision:<5} {input_path}")
    return 0


def cmd_telemetry_grep(args: argparse.Namespace) -> int:
    """Search telemetry events using regex pattern matching."""
    pattern_str: str = args.pattern
    pattern = re.compile(pattern_str)
    files = _iter_session_files(TELEMETRY_ROOT)
    events = _read_events(files)
    matches = [e for e in events if pattern.search(json.dumps(e))]
    for e in matches:
        print(json.dumps(e))
    return 0


def cmd_telemetry_diff(args: argparse.Namespace) -> int:
    """Diff hook-firing decision rates between two telemetry sessions."""
    files = {f.stem: f for f in _iter_session_files(TELEMETRY_ROOT)}
    session_a: str = args.session_a
    session_b: str = args.session_b
    missing = [s for s in (session_a, session_b) if s not in files]
    if missing:
        for name in missing:
            print(f"session not found: {name}", file=sys.stderr)
        return 1
    events_a = _read_events([files[session_a]])
    events_b = _read_events([files[session_b]])
    counts_a = Counter(str(e.get("hook_decision")) for e in events_a)
    counts_b = Counter(str(e.get("hook_decision")) for e in events_b)
    print(f"{'decision':<10} {'A':>5} {'B':>5} {'delta':>7}")
    decisions = sorted(set(counts_a) | set(counts_b))
    for key in decisions:
        a, b = counts_a.get(key, 0), counts_b.get(key, 0)
        print(f"{key:<10} {a:>5} {b:>5} {b - a:>+7}")
    return 0


def cmd_telemetry_export(args: argparse.Namespace) -> int:
    """Bundle local telemetry session logs into JSONL export payload."""
    pii_reviewed: bool = getattr(args, "i_understand_pii_implications", False)
    if not pii_reviewed:
        print(
            "ERROR: --i-understand-pii-implications is required to export.\n"
            "Local telemetry may contain file paths and tool inputs. By exporting\n"
            "you confirm you have reviewed the data for PII before uploading.",
            file=sys.stderr,
        )
        return 2
    files = _iter_session_files(TELEMETRY_ROOT)
    out_arg: str | None = args.out
    out = Path(out_arg) if out_arg else TELEMETRY_ROOT / "exports" / "export.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    events = _read_events(files)
    with out.open("w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    print(f"exported {len(events)} events to {out}")
    return 0


def cmd_telemetry_config(args: argparse.Namespace) -> int:
    """Set key/value properties in local telemetry config file."""
    config_path = TELEMETRY_ROOT / "config.properties"
    TELEMETRY_ROOT.mkdir(parents=True, exist_ok=True)
    existing: dict[str, str] = {}
    if config_path.exists():
        for line in config_path.read_text().splitlines():
            if ":" in line and not line.strip().startswith("#"):
                k, v = line.split(":", 1)
                existing[k.strip()] = v.strip()
    key: str = args.key
    value: str = args.value
    existing[key] = value
    config_path.write_text("\n".join(f"{k}: {v}" for k, v in sorted(existing.items())) + "\n")
    print(f"set {key}={value} in {config_path}")
    return 0


def cmd_telemetry_schema(args: argparse.Namespace) -> int:
    """Print canonical telemetry JSON Schema."""
    if not SCHEMA_PATH.exists():
        print(f"error: schema file not found: {SCHEMA_PATH}", file=sys.stderr)
        return 1
    schema: object = json.loads(SCHEMA_PATH.read_text())
    print(json.dumps(schema, indent=2))
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Auto-detect project languages and frameworks, then install matching packs + hooks.

    Inspects target project manifest files across 9 supported language ecosystems
    and deploys matching language packs, hooks, and best-practice skills.

    Args:
        args: Parsed CLI namespace containing `target` (str directory path).

    Returns:
        0 on successful auto-detection & deployment, 1 if target directory missing.
    """
    target_dir = Path(args.target).resolve()
    if not target_dir.is_dir():
        print(f"error: target directory '{target_dir}' does not exist", file=sys.stderr)
        return 1

    packs_to_install: set[str] = {"best-practices", "hooks", "pre-commit"}

    # Project Manifest Auto-Detection Rules across 9 languages
    if any(
        (target_dir / f).exists()
        for f in ("pyproject.toml", "setup.py", "requirements.txt", "Pipfile", "poetry.lock")
    ):
        packs_to_install.add("python")

    if (target_dir / "Cargo.toml").exists():
        packs_to_install.add("rust")
        packs_to_install.add("fallow")

    if (target_dir / "package.json").exists() or (target_dir / "tsconfig.json").exists():
        packs_to_install.add("typescript")
        packs_to_install.add("web-frontend")
        packs_to_install.add("fallow")

    if (target_dir / "go.mod").exists():
        packs_to_install.add("go")

    if any(
        (target_dir / f).exists() for f in ("CMakeLists.txt", "Makefile", "compile_commands.json")
    ):
        packs_to_install.add("cpp")

    if any((target_dir / f).exists() for f in ("pom.xml", "build.gradle", "build.gradle.kts")):
        packs_to_install.add("java")

    if any((target_dir / f).exists() for f in ("Gemfile", ".rubocop.yml", "Rakefile")):
        packs_to_install.add("ruby")

    if (target_dir / "mix.exs").exists():
        packs_to_install.add("elixir")

    if (
        any(target_dir.glob("*.csproj"))
        or any(target_dir.glob("*.sln"))
        or (target_dir / "global.json").exists()
    ):
        packs_to_install.add("csharp")

    print(f"heretek init: Auto-detected project at {target_dir}")
    print(
        f"Deploying {len(packs_to_install)} matching plugin pack(s): {', '.join(sorted(packs_to_install))}"
    )

    for pack in sorted(packs_to_install):
        dummy_args = argparse.Namespace(pack_name=pack, target=str(target_dir))
        res = cmd_install(dummy_args)
        if res != 0:
            print(f"error: failed to install pack '{pack}'", file=sys.stderr)
            return res

    print("heretek init: Repository initialization complete!")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Display Heretek quality status scorecard and deployed plugin inventory.

    Calculates the 4-Pillar Agentic Readiness Score (0-100 pts) based on:
    - Pillar 1: Deterministic Quality Gates (.claude/hooks.json)
    - Pillar 2: Pre-Commit Guard (.pre-commit-config.yaml)
    - Pillar 3: Context Hygiene (AGENTS.md / CLAUDE.md / README.md)
    - Pillar 4: Best Practices & Audit Packs (best-practices / quality-audit)

    Args:
        args: Parsed CLI namespace containing `target` (str directory path).

    Returns:
        0 on status calculation pass, 1 if target directory missing.
    """
    target_dir = Path(args.target).resolve()
    if not target_dir.is_dir():
        print(f"error: target directory '{target_dir}' does not exist", file=sys.stderr)
        return 1

    claude_dir = target_dir / ".claude"
    plugins_dir = claude_dir / "plugins"
    hooks_file = claude_dir / "hooks.json"
    precommit_file = target_dir / ".pre-commit-config.yaml"

    installed_plugins: list[str] = []
    if plugins_dir.is_dir():
        installed_plugins = [d.name for d in plugins_dir.iterdir() if d.is_dir()]

    # Calculate 4-Pillar Agentic Readiness Score (25 pts per pillar)
    score = 0
    if hooks_file.is_file():
        score += 25
    if precommit_file.is_file():
        score += 25
    if any((target_dir / f).is_file() for f in ("AGENTS.md", "CLAUDE.md", "README.md")):
        score += 25
    if "best-practices" in installed_plugins or "quality-audit" in installed_plugins:
        score += 25

    print("┌──────────────────────────────────────────────────────────┐")
    print("│                 HERETEK QUALITY SCORECARD                │")
    print("├──────────────────────────────────────────────────────────┤")
    print(f"│ Target Directory : {target_dir!s:<38} │")
    print(f"│ Readiness Score  : {score}/100 pts                              │")
    print(f"│ Pre-Commit Guard : {'[ACTIVE]' if precommit_file.is_file() else '[INACTIVE]':<38} │")
    print(f"│ Hook Interceptor : {'[INSTALLED]' if hooks_file.is_file() else '[MISSING]':<38} │")
    print(f"│ Deployed Packs   : {len(installed_plugins):<2} pack(s)                            │")
    for pack in sorted(installed_plugins):
        print(f"│   - {pack:<50} │")
    print("└──────────────────────────────────────────────────────────┘")
    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    """Benchmark local fast-gate hook execution latencies to enforce <100ms SLA.

    Args:
        args: Parsed CLI namespace.

    Returns:
        0 if benchmark latency <500ms, 1 if latency exceeds threshold.
    """
    import time

    from plugins.hooks.scripts.fast_gate import dispatch

    t0 = time.perf_counter()
    dispatch(Path("scripts/heretek_cli.py"))
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    print("┌──────────────────────────────────────────────────────────┐")
    print("│            HERETEK FAST-GATE LATENCY BENCHMARK          │")
    print("├──────────────────────────────────────────────────────────┤")
    print(f"│ Fast-Gate Execution Latency : {elapsed_ms:.2f} ms                  │")
    status_str = "[PASS <100ms SLA]" if elapsed_ms < 100.0 else "[WARN Exceeds 100ms]"
    print(f"│ SLA Compliance Boundary    : {status_str:<28} │")
    print("└──────────────────────────────────────────────────────────┘")
    return 0 if elapsed_ms < 500.0 else 1


def cmd_eval(args: argparse.Namespace) -> int:
    """Run Harbor TerminalBench 2.0 A/B evaluation suite locally or in CI.

    Args:
        args: Parsed CLI namespace containing model, tasks, concurrent, and output.

    Returns:
        0 on evaluation completion pass, 1 on failure.
    """
    import os
    import subprocess

    env = os.environ.copy()
    env["ANTHROPIC_MODEL"] = args.model
    env["HERETEK_N_TASKS"] = str(args.tasks)
    env["HERETEK_N_CONCURRENT"] = str(args.concurrent)
    env["HERETEK_PLUGIN_DIR"] = str(REPO_ROOT / "plugins")

    script_path = REPO_ROOT / "scripts" / "terminal_bench_ab.sh"
    res = subprocess.run(["bash", str(script_path)], env=env, cwd=REPO_ROOT)
    return res.returncode


def build_parser() -> argparse.ArgumentParser:
    """Build top-level ArgumentParser for Heretek CLI."""
    parser = argparse.ArgumentParser(
        prog="heretek",
        description="heretek marketplace & distribution CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # heretek status [--target TARGET_DIR]
    status_parser = sub.add_parser("status", help="display repository quality scorecard & status")
    status_parser.add_argument(
        "--target", default=".", help="target project directory (default: current dir)"
    )
    status_parser.set_defaults(func=cmd_status)

    # heretek metrics
    metrics_parser = sub.add_parser("metrics", help="benchmark fast-gate hook execution latencies")
    metrics_parser.set_defaults(func=cmd_metrics)

    # heretek eval [--model MODEL] [--tasks TASKS] [--concurrent CONCURRENT]
    eval_parser = sub.add_parser("eval", help="run Harbor TerminalBench 2.0 A/B evaluation harness")
    eval_parser.add_argument(
        "--model", default="claude-sonnet-5-20260301", help="evaluation model name"
    )
    eval_parser.add_argument(
        "--tasks", default="8", help="number of tasks ('8' for quick subset, or 'all')"
    )
    eval_parser.add_argument("--concurrent", default="8", help="per-agent trial concurrency level")
    eval_parser.set_defaults(func=cmd_eval)

    # heretek init [--target TARGET_DIR]
    init_parser = sub.add_parser(
        "init", help="auto-detect project language and install matching packs"
    )
    init_parser.add_argument(
        "--target", default=".", help="target project directory (default: current dir)"
    )
    init_parser.set_defaults(func=cmd_init)

    # heretek install <pack-name> [--target TARGET_DIR]
    install_parser = sub.add_parser("install", help="install a plugin package into target project")
    install_parser.add_argument("pack_name", help="name of plugin package in plugins/")
    install_parser.add_argument(
        "--target", default=".", help="target project directory (default: current dir)"
    )
    install_parser.set_defaults(func=cmd_install)

    # heretek validate [--repo-root PATH]
    validate_parser = sub.add_parser("validate", help="validate plugin & marketplace manifests")
    validate_parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    validate_parser.add_argument(
        "--schemas-dir", type=Path, default=REPO_ROOT / "tests" / "schemas"
    )
    validate_parser.set_defaults(func=cmd_validate)

    # heretek build-catalog [--catalog PATH] [--output PATH]
    catalog_parser = sub.add_parser(
        "build-catalog", help="regenerate marketplace.json from catalog.yaml"
    )
    catalog_parser.add_argument(
        "--catalog", type=Path, default=REPO_ROOT / "catalog" / "catalog.yaml"
    )
    catalog_parser.add_argument(
        "--output", type=Path, default=REPO_ROOT / ".claude-plugin" / "marketplace.json"
    )
    catalog_parser.set_defaults(func=cmd_build_catalog)

    # heretek telemetry ...
    tel = sub.add_parser("telemetry", help="local hook event log inspection")
    tel_sub = tel.add_subparsers(dest="subcommand", required=True)

    show = tel_sub.add_parser("show", help="show events")
    show.add_argument(
        "--session",
        help="filter by session id (substring match; e.g., '2026-08-08' matches all sessions in that date folder)",
    )
    show.add_argument("--tool", help="filter by tool name")
    show.add_argument("--since", help="filter by timestamp prefix")
    show.set_defaults(func=cmd_telemetry_show)

    grep = tel_sub.add_parser("grep", help="regex search across all sessions")
    grep.add_argument("pattern")
    grep.set_defaults(func=cmd_telemetry_grep)

    diff = tel_sub.add_parser("diff", help="diff two sessions' hook-firing rates")
    diff.add_argument("session_a")
    diff.add_argument("session_b")
    diff.set_defaults(func=cmd_telemetry_diff)

    exp = tel_sub.add_parser("export", help="bundle for upload (opt-in)")
    exp.add_argument("--out", help="output path")
    exp.add_argument(
        "--i-understand-pii-implications",
        action="store_true",
        dest="i_understand_pii_implications",
        help="confirm PII review before exporting",
    )
    exp.set_defaults(func=cmd_telemetry_export)

    cfg = tel_sub.add_parser("config", help="read/write config.properties")
    cfg_sub = cfg.add_subparsers(dest="cfg_subcommand", required=True)
    cfg_set = cfg_sub.add_parser("set", help="set a config key")
    cfg_set.add_argument("key")
    cfg_set.add_argument("value")
    cfg_set.set_defaults(func=cmd_telemetry_config)

    sch = tel_sub.add_parser("schema", help="print telemetry JSON Schema")
    sch.set_defaults(func=cmd_telemetry_schema)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI execution entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    return func(args)  # type: ignore[no-any-return]


if __name__ == "__main__":
    sys.exit(main())
