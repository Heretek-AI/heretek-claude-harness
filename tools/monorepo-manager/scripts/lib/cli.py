"""CLI orchestration for init-harness.sh.

The Bash script delegates to this module via `python -m scripts.lib.cli`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.lib import (
    render_agents,
    render_ci,
    render_configs,
    render_hooks,
    render_mcp,
    render_seed,
    render_settings,
    render_skills,
    render_tracking,
)
from scripts.lib.contract_hash import compute_contract_hash, compute_seeds_hash


def _write_files(target: Path, files: dict[str, str]) -> None:
    import stat

    for rel, content in files.items():
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        # Spec §10: child scripts must be executable. Per spec §10, the
        # generated `scripts/seed-issues.sh` is a shell entry point and
        # must be runnable directly from the child repo's working dir.
        if rel == "scripts/seed-issues.sh":
            dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _bundle(name: str, stack: str, org: str, project_id: str, default_model: str) -> dict[str, str]:
    files: dict[str, str] = {}

    if stack == "python":
        test_cmd = "pytest"
        build_cmd = "python -m build"
        lint_cmd = "ruff check ."
        run_cmd = "python -m heretek_builds --help"
        language = "Python 3.11+"
        package_manager = "pip, setuptools"
        os_arch = "Linux x86_64"
        project_summary = "CI/CD registry for llama.cpp family builds."
        sonar_key = f"{org}_{name}"
        skills = [
            {
                "name": "heretek-manifest-codegen",
                "description": "Generate manifest.json from targets/*/build.sh.",
                "allowed_tools": ["Bash", "Read"],
                "required_skills": [],
                "body": "1. read targets/*/build.sh\n2. emit manifest.json\n3. validate against schemas/manifest.schema.json",
            },
            {
                "name": "heretek-upstream-sync",
                "description": "Test a new llama.cpp upstream SHA before promoting to a release.",
                "allowed_tools": ["Bash"],
                "required_skills": [],
                "body": "1. checkout upstream SHA\n2. run audit_matrix.py\n3. report PR-ready status",
            },
        ]
        mcp_servers = {
            "github": {
                "description": "Official GitHub MCP",
                "transport": "stdio",
                "command": "github-mcp",
                "args": ["--owner", org, "--repo", name],
                "env": {"GITHUB_TOKEN": None},
                "timeoutSeconds": 30,
            },
            "sonarqube": {
                "description": "SonarCloud MCP",
                "transport": "stdio",
                "command": "sonarqube-mcp",
                "args": ["--project", sonar_key],
                "env": {"SONAR_TOKEN": None, "SONAR_HOST_URL": None},
            },
        }
    elif stack == "node":
        test_cmd = "npm test"
        build_cmd = "npm run build"
        lint_cmd = "npx eslint ."
        run_cmd = "npx heretek-manager --help"
        language = "TypeScript 5 + Node 20"
        package_manager = "npm"
        os_arch = "Linux x86_64"
        project_summary = "Local NPM CLI + WebUI for the Heretek AI runtime."
        sonar_key = f"{org}_{name}"
        skills = [
            {
                "name": "heretek-strix-halo-audit",
                "description": "Audit host hardware and recommend a backend.",
                "allowed_tools": ["Bash"],
                "required_skills": [],
                "body": "1. shell out to nvidia-smi/rocminfo/vulkaninfo\n2. parse output\n3. recommend backend",
            },
            {
                "name": "heretek-symlink-swap",
                "description": "Apply the atomic symlink swap recipe.",
                "allowed_tools": ["Bash", "Edit"],
                "required_skills": [],
                "body": "1. write to a temp symlink\n2. rename atomically\n3. verify symlink target",
            },
            {
                "name": "heretek-manifest-fetch",
                "description": "Fetch the llama-builds manifest with retries.",
                "allowed_tools": ["Bash"],
                "required_skills": [],
                "body": "1. fetch https://heretek-ai.github.io/llama-builds/manifest.json\n2. retry up to 3 times\n3. verify SHA-256 against sha256sum.txt",
            },
        ]
        mcp_servers = {
            "github": {
                "description": "Official GitHub MCP",
                "transport": "stdio",
                "command": "github-mcp",
                "args": ["--owner", org, "--repo", name],
                "env": {"GITHUB_TOKEN": None},
                "timeoutSeconds": 30,
            },
            "sonarqube": {
                "description": "SonarCloud MCP",
                "transport": "stdio",
                "command": "sonarqube-mcp",
                "args": ["--project", sonar_key],
                "env": {"SONAR_TOKEN": None, "SONAR_HOST_URL": None},
            },
        }
    else:
        raise ValueError(f"unknown stack '{stack}'")

    files.update(
        render_agents.render_agents(
            {
                "name": name,
                "stack": stack,
                "language": language,
                "package_manager": package_manager,
                "os_arch": os_arch,
                "project_summary": project_summary,
                "build_cmd": build_cmd,
                "test_cmd": test_cmd,
                "lint_cmd": lint_cmd,
                "run_cmd": run_cmd,
                "sonar_key": sonar_key,
                "project_url": f"https://github.com/orgs/{org}/projects/{project_id}",
                "super_linter_config_path": ".github/linters/",
                "seed_url": f"https://github.com/{org}/monorepo-manager/blob/main/seeds/{name}.yaml",
            }
        )
    )
    files.update(render_skills.render_skills(skills))
    files[".mcp.json"] = render_mcp.render_mcp_named(mcp_servers)
    files.update(render_settings.render_settings(stack, default_model=default_model))
    files.update(render_hooks.render_hooks(stack))
    files.update(render_ci.render_ci(stack, test_cmd=test_cmd))
    files.update(render_configs.render_configs(stack, sonar_key=sonar_key, project_name=name))
    files.update(render_tracking.render_issue_templates(org=org, repo=name))
    files.update(render_tracking.render_pr_template())
    files.update(
        render_tracking.render_project_automation(org=org, repo=name, project_id=project_id)
    )
    files.update(render_tracking.render_labeler())
    files.update(render_tracking.render_contributing(org=org, repo=name))
    files.update(render_seed.render_labels())
    # Per spec §10: the child does NOT receive a copy of seeds/<repo>.yaml.
    # The umbrella's seeds/ is the canonical source; the child fetches it at
    # runtime via scripts/seed-issues.sh --seed-url (or --seed-file override).
    files.update(render_seed.render_seed_issues_script(org=org, repo=name, slug=name))

    return files


def _bake_contract_hash(target: Path, spec_path: Path, section_anchor: str) -> None:
    # Mix the rendered seed files into the contract hash so editing any
    # seeds/*.yaml invalidates downstream installs (per spec §10).
    digest = compute_contract_hash(spec_path, section_anchor, seeds_hash=compute_seeds_hash())
    (target / ".heretek-harness.json").write_text(
        json.dumps({"contract_hash": digest, "section_anchor": section_anchor}, indent=2)
    )


def _existing_contract_hash(target: Path) -> dict | None:
    p = target / ".heretek-harness.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="init-harness")
    parser.add_argument("--target", required=True)
    parser.add_argument("--name", required=False)
    parser.add_argument("--stack", required=False, choices=["python", "node"])
    parser.add_argument("--org", default="Heretek-AI")
    parser.add_argument("--project-id", default="0")
    parser.add_argument("--default-model", default="sonnet")
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite a generated harness whose contract-hash has drifted",
    )
    parser.add_argument(
        "--refresh-hooks",
        action="store_true",
        help="re-emit hook files only (after legitimate hook edits)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="validate the existing harness without writing",
    )
    parser.add_argument(
        "--spec-path",
        default=str(
            Path(__file__).parents[2]
            / "docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md"
        ),
    )
    parser.add_argument("--section-anchor", default="4. Layer 1")
    args = parser.parse_args(argv)

    if not args.verify and (not args.name or not args.stack):
        parser.error("--name and --stack are required (unless --verify is passed)")

    target = Path(args.target).resolve()
    target.mkdir(parents=True, exist_ok=True)

    if args.verify:
        return run_verify(target, args.spec_path, args.section_anchor)

    existing = _existing_contract_hash(target)
    if existing and not args.force:
        current = compute_contract_hash(
            Path(args.spec_path), args.section_anchor, seeds_hash=compute_seeds_hash()
        )
        if existing["contract_hash"] != current:
            print(
                f"contract drift detected: existing={existing['contract_hash']} "
                f"current={current}. Re-run with --force to regenerate.",
                file=sys.stderr,
            )
            return 2

    if args.refresh_hooks:
        files = render_hooks.render_hooks(args.stack)
        _write_files(target, files)
        _bake_contract_hash(target, Path(args.spec_path), args.section_anchor)
        return 0

    files = _bundle(args.name, args.stack, args.org, args.project_id, args.default_model)
    _write_files(target, files)
    _bake_contract_hash(target, Path(args.spec_path), args.section_anchor)
    return 0


def run_verify(target: Path, spec_path: str, section_anchor: str) -> int:
    """Validate the on-disk harness against the contract."""
    from scripts.lib import validate_agents, validate_mcp, validate_settings, validate_skills

    errors: list[str] = []
    agents = target / "AGENTS.md"
    if agents.is_file():
        errors.extend(f"AGENTS.md: {e}" for e in validate_agents.validate_agents(str(agents)))
    mcp = target / ".mcp.json"
    if mcp.is_file():
        errors.extend(f".mcp.json: {e}" for e in validate_mcp.validate_mcp(str(mcp)))
    settings = target / ".claude" / "settings.json"
    if settings.is_file():
        errors.extend(
            f"settings.json: {e}" for e in validate_settings.validate_settings(str(settings))
        )
    skills_dir = target / ".claude" / "skills"
    if skills_dir.is_dir():
        for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            errors.extend(
                f"skills/{skill.name}: {e}" for e in validate_skills.validate_skill(str(skill))
            )
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
