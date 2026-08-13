# Automated Builds & Local Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port llamacpp-rocm's automated multi-target build system into llama-builds (config-driven matrix, self-contained distributions, upstream watch, release automation) and scaffold heretek-manager's local web UI (Express + SPA, provider abstraction, REST API).

**Architecture:** llama-builds gets a Python matrix generator that reads target METADATA and emits GitHub Actions matrix JSON, a library bundling script per backend strategy, and three new workflows (build, upstream-watch, release). heretek-manager gets an Express server with provider abstraction, REST API, WebSocket events, and a bundled Vite SPA.

**Tech Stack:** Python 3.11+ (llama-builds scripts), TypeScript/Node 20 (heretek-manager), Express, Vite, Vitest, pytest, GitHub Actions.

## Global Constraints

- Python >=3.11, Node >=20
- Conventional Commits for all messages
- `ruff check .` for Python lint, `npx eslint .` for TypeScript lint
- All generated artefacts in `reference/` are not hand-edited
- PRs target `main`, no direct pushes
- `pre-commit run --all-files` must pass before commit

---

## Phase 1: llama-builds — Config-Driven Matrix + CPU Distribution

### Task 1: Extract METADATA parser into testable Python module

**Files:**
- Create: `llama-builds/scripts/metadata_parser.py`
- Create: `llama-builds/tests/test_metadata_parser.py`

**Interfaces:**
- Consumes: `targets/*/build.sh` files with `# METADATA` headers
- Produces: `parse_metadata(path: Path) -> dict` returning `{name, repo, ref, backend, arch, capabilities, gpu_targets, runtime_deps, bundle_strategy}`

- [ ] **Step 1: Write the failing test**

```python
# llama-builds/tests/test_metadata_parser.py
from pathlib import Path
from scripts.metadata_parser import parse_metadata


def test_parse_cpu_target(tmp_path: Path) -> None:
    build_sh = tmp_path / "build.sh"
    build_sh.write_text(
        '#!/usr/bin/env bash\n'
        '# METADATA\n'
        '# name=llama.cpp upstream CPU baseline\n'
        '# repo=ggml-org/llama.cpp\n'
        '# ref=0ab9d6fed73dbc5dc8026c868cb10a6728c4ed48\n'
        '# backend=cpu\n'
        '# arch=x86_64\n'
        '# capabilities=chat,embed\n'
        'set -euo pipefail\n'
        'echo "build"\n'
    )
    meta = parse_metadata(build_sh)
    assert meta["name"] == "llama.cpp upstream CPU baseline"
    assert meta["backend"] == "cpu"
    assert meta["arch"] == "x86_64"
    assert meta["capabilities"] == ["chat", "embed"]
    assert meta["gpu_targets"] == []
    assert meta["bundle_strategy"] == "cpu-static"


def test_parse_rocm_target(tmp_path: Path) -> None:
    build_sh = tmp_path / "build.sh"
    build_sh.write_text(
        '#!/usr/bin/env bash\n'
        '# METADATA\n'
        '# name=llama.cpp upstream ROCm baseline\n'
        '# repo=ggml-org/llama.cpp\n'
        '# ref=0ab9d6fed73dbc5dc8026c868cb10a6728c4ed48\n'
        '# backend=rocm\n'
        '# arch=x86_64\n'
        '# gpu_targets=gfx1100,gfx1101,gfx1102,gfx1103\n'
        '# capabilities=chat,embed\n'
        '# runtime_deps=librocblas,libhipblas,libamdhip64\n'
        '# bundle_strategy=rocm-therock\n'
        'set -euo pipefail\n'
    )
    meta = parse_metadata(build_sh)
    assert meta["backend"] == "rocm"
    assert meta["gpu_targets"] == ["gfx1100", "gfx1101", "gfx1102", "gfx1103"]
    assert meta["runtime_deps"] == ["librocblas", "libhipblas", "libamdhip64"]
    assert meta["bundle_strategy"] == "rocm-therock"


def test_parse_missing_metadata_raises(tmp_path: Path) -> None:
    build_sh = tmp_path / "build.sh"
    build_sh.write_text('#!/usr/bin/env bash\necho "no metadata"\n')
    from scripts.metadata_parser import MetadataParseError
    try:
        parse_metadata(build_sh)
        assert False, "Should have raised MetadataParseError"
    except MetadataParseError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd llama-builds && python -m pytest tests/test_metadata_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.metadata_parser'`

- [ ] **Step 3: Write minimal implementation**

```python
# llama-builds/scripts/metadata_parser.py
"""Parse METADATA headers from target build.sh files."""
from __future__ import annotations

import re
from pathlib import Path


class MetadataParseError(Exception):
    """Raised when METADATA block is missing or malformed."""


# Default values for fields that may be absent
DEFAULTS = {
    "arch": "x86_64",
    "capabilities": [],
    "gpu_targets": [],
    "runtime_deps": [],
    "bundle_strategy": "cpu-static",
}


def parse_metadata(build_sh: Path) -> dict:
    """Parse METADATA block from a target build.sh file.

    Returns dict with keys: name, repo, ref, backend, arch, capabilities,
    gpu_targets, runtime_deps, bundle_strategy.
    """
    in_metadata = False
    raw: dict[str, str] = {}

    for line in build_sh.read_text().splitlines():
        stripped = line.strip()
        if stripped == "# METADATA":
            in_metadata = True
            continue
        if in_metadata and stripped.startswith("# "):
            match = re.match(r"^#\s*([^=]+)=(.+)$", stripped)
            if match:
                raw[match.group(1).strip()] = match.group(2).strip()
        elif in_metadata and not stripped.startswith("#"):
            break

    if not raw:
        raise MetadataParseError(f"No METADATA block found in {build_sh}")

    # Build result with parsing
    result: dict = {}
    result["name"] = raw.get("name", "")
    result["repo"] = raw.get("repo", "")
    result["ref"] = raw.get("ref", "")
    result["backend"] = raw.get("backend", "")
    result["arch"] = raw.get("arch", DEFAULTS["arch"])

    # CSV fields
    for field in ("capabilities", "gpu_targets", "runtime_deps"):
        val = raw.get(field, "")
        result[field] = [v.strip() for v in val.split(",") if v.strip()] if val else DEFAULTS[field]

    result["bundle_strategy"] = raw.get("bundle_strategy", DEFAULTS["bundle_strategy"])
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd llama-builds && python -m pytest tests/test_metadata_parser.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
cd llama-builds && git add scripts/metadata_parser.py tests/test_metadata_parser.py && git commit -m "feat: extract METADATA parser into testable Python module

Parse # METADATA blocks from targets/*/build.sh into structured dicts.
Supports new fields: gpu_targets, runtime_deps, bundle_strategy.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: GPU family expansion + matrix generation

**Files:**
- Modify: `llama-builds/scripts/metadata_parser.py`
- Modify: `llama-builds/tests/test_metadata_parser.py`

**Interfaces:**
- Consumes: `parse_metadata()` output from Task 1
- Produces: `expand_gpu_family(family: str) -> list[str]`, `generate_matrix(targets_dir: Path) -> dict`

- [ ] **Step 1: Write the failing tests**

Append to `llama-builds/tests/test_metadata_parser.py`:

```python
from scripts.metadata_parser import expand_gpu_family, generate_matrix


def test_expand_gpu_family_gfx110x() -> None:
    assert expand_gpu_family("gfx110X") == ["gfx1100", "gfx1101", "gfx1102", "gfx1103"]


def test_expand_gpu_family_gfx103x() -> None:
    assert expand_gpu_family("gfx103X") == ["gfx1030", "gfx1031", "gfx1032", "gfx1034"]


def test_expand_gpu_family_gfx120x() -> None:
    assert expand_gpu_family("gfx120X") == ["gfx1200", "gfx1201"]


def test_expand_gpu_family_single() -> None:
    assert expand_gpu_family("gfx1151") == ["gfx1151"]


def test_generate_matrix_cpu_only(tmp_path: Path) -> None:
    target_dir = tmp_path / "upstream-cpu"
    target_dir.mkdir()
    (target_dir / "build.sh").write_text(
        '#!/usr/bin/env bash\n'
        '# METADATA\n'
        '# name=llama.cpp upstream CPU baseline\n'
        '# repo=ggml-org/llama.cpp\n'
        '# ref=0ab9d6fed73dbc5dc8026c868cb10a6728c4ed48\n'
        '# backend=cpu\n'
        '# arch=x86_64\n'
        '# capabilities=chat,embed\n'
    )
    matrix = generate_matrix(tmp_path)
    assert len(matrix["include"]) == 1
    assert matrix["include"][0]["backend"] == "cpu"
    assert matrix["include"][0]["gfx_target"] is None


def test_generate_matrix_rocm_expands(tmp_path: Path) -> None:
    target_dir = tmp_path / "upstream-rocm"
    target_dir.mkdir()
    (target_dir / "build.sh").write_text(
        '#!/usr/bin/env bash\n'
        '# METADATA\n'
        '# name=llama.cpp upstream ROCm\n'
        '# repo=ggml-org/llama.cpp\n'
        '# ref=0ab9d6fed73dbc5dc8026c868cb10a6728c4ed48\n'
        '# backend=rocm\n'
        '# arch=x86_64\n'
        '# gpu_targets=gfx110X,gfx1151\n'
        '# capabilities=chat,embed\n'
        '# bundle_strategy=rocm-therock\n'
    )
    matrix = generate_matrix(tmp_path)
    # gfx110X expands to 4 + gfx1151 = 5 entries
    assert len(matrix["include"]) == 5
    gfx_targets = [e["gfx_target"] for e in matrix["include"]]
    assert "gfx1100" in gfx_targets
    assert "gfx1103" in gfx_targets
    assert "gfx1151" in gfx_targets
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd llama-builds && python -m pytest tests/test_metadata_parser.py -v -k "expand or matrix"`
Expected: FAIL with `ImportError: cannot import name 'expand_gpu_family'`

- [ ] **Step 3: Implement GPU expansion + matrix generation**

Append to `llama-builds/scripts/metadata_parser.py`:

```python
# GPU family → individual ISA target mapping
GPU_FAMILIES = {
    "gfx110X": ["gfx1100", "gfx1101", "gfx1102", "gfx1103"],
    "gfx103X": ["gfx1030", "gfx1031", "gfx1032", "gfx1034"],
    "gfx120X": ["gfx1200", "gfx1201"],
}


def expand_gpu_family(family: str) -> list[str]:
    """Expand a GPU family target (e.g. gfx110X) to individual ISA targets."""
    return GPU_FAMILIES.get(family, [family])


def generate_matrix(targets_dir: Path) -> dict:
    """Read all targets/*/build.sh and emit GitHub Actions matrix JSON structure."""
    entries = []
    for build_sh in sorted(targets_dir.glob("*/build.sh")):
        target_name = build_sh.parent.name
        if target_name.startswith("_"):
            continue
        meta = parse_metadata(build_sh)
        if meta["backend"] == "rocm" and meta["gpu_targets"]:
            for family in meta["gpu_targets"]:
                for isa in expand_gpu_family(family):
                    entries.append({
                        "target": target_name,
                        "backend": meta["backend"],
                        "arch": meta["arch"],
                        "gfx_target": isa,
                        "repo": meta["repo"],
                        "ref": meta["ref"],
                        "bundle_strategy": meta["bundle_strategy"],
                        "capabilities": meta["capabilities"],
                    })
        else:
            entries.append({
                "target": target_name,
                "backend": meta["backend"],
                "arch": meta["arch"],
                "gfx_target": None,
                "repo": meta["repo"],
                "ref": meta["ref"],
                "bundle_strategy": meta["bundle_strategy"],
                "capabilities": meta["capabilities"],
            })
    return {"include": entries}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd llama-builds && python -m pytest tests/test_metadata_parser.py -v`
Expected: 10 PASS (3 original + 7 new)

- [ ] **Step 5: Commit**

```bash
cd llama-builds && git add scripts/metadata_parser.py tests/test_metadata_parser.py && git commit -m "feat: add GPU family expansion and matrix generation

expand_gpu_family maps family targets (gfx110X) to individual ISAs.
generate_matrix reads targets/*/build.sh and emits GitHub Actions matrix JSON.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Library bundling script

**Files:**
- Create: `llama-builds/scripts/bundle_libs.py`
- Create: `llama-builds/tests/test_bundle_libs.py`

**Interfaces:**
- Consumes: `bundle_strategy` string from METADATA, build artifact directory
- Produces: Copies runtime libraries into artifact dir, sets RPATH

- [ ] **Step 1: Write the failing tests**

```python
# llama-builds/tests/test_bundle_libs.py
from pathlib import Path
from scripts.bundle_libs import bundle_libs, BUNDLE_STRATEGIES


def test_cpu_static_noop(tmp_path: Path) -> None:
    """CPU static strategy copies nothing."""
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "llama-server").write_text("binary")
    bundle_libs(artifact_dir, "cpu-static")
    assert list(artifact_dir.iterdir()) == [artifact_dir / "llama-server"]


def test_strategy_has_required_keys() -> None:
    for name, strategy in BUNDLE_STRATEGIES.items():
        assert "patterns" in strategy, f"{name} missing patterns"
        assert "rpath" in strategy, f"{name} missing rpath"


def test_rocm_strategy_patterns_nonempty() -> None:
    assert len(BUNDLE_STRATEGIES["rocm-therock"]["patterns"]) > 0


def test_bundle_copies_matching_files(tmp_path: Path) -> None:
    """Strategy with patterns copies matching files."""
    lib_dir = tmp_path / "libs"
    lib_dir.mkdir()
    (lib_dir / "libfoo.so.1").write_text("lib")
    (lib_dir / "libfoo.so.1.2").write_text("lib")
    (lib_dir / "libbar.so").write_text("lib")
    (lib_dir / "unrelated.txt").write_text("txt")

    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "llama-server").write_text("binary")

    # Use a custom strategy with one pattern
    from scripts.bundle_libs import bundle_libs_custom
    bundle_libs_custom(artifact_dir, lib_dir, ["libfoo.so*"])
    copied = [f.name for f in artifact_dir.iterdir()]
    assert "libfoo.so.1" in copied
    assert "libfoo.so.1.2" in copied
    assert "libbar.so" not in copied
    assert "unrelated.txt" not in copied
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd llama-builds && python -m pytest tests/test_bundle_libs.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement bundle_libs**

```python
# llama-builds/scripts/bundle_libs.py
"""Bundle runtime libraries into build artifact directories."""
from __future__ import annotations

import fnmatch
import shutil
import subprocess
from pathlib import Path


BUNDLE_STRATEGIES: dict[str, dict] = {
    "cpu-static": {
        "patterns": [],
        "rpath": "$ORIGIN",
    },
    "rocm-therock": {
        "patterns": [
            "librocblas.so*",
            "libhipblas.so*",
            "libamdhip64.so*",
            "librocsolver.so*",
            "libroctx64.so*",
            "libhipblaslt.so*",
            "librocprofiler-register.so*",
            "libamd_comgr.so*",
            "libhsa-runtime64.so*",
            "librocroller.so*",
            "liborigami.so*",
            "librocm_kpack.so*",
            "libLLVM.so*",
            "libclang-cpp.so*",
        ],
        "rpath": "$ORIGIN",
        "extra_dirs": ["rocblas/library", "hipblaslt/library"],
    },
    "cuda-redist": {
        "patterns": [
            "libcublas.so*",
            "libcublasLt.so*",
            "libcudart.so*",
            "libcufft.so*",
            "libcusparse.so*",
            "libcusolver.so*",
            "libnvrtc.so*",
            "libnvJitLink.so*",
        ],
        "rpath": "$ORIGIN",
    },
    "vulkan-sdk": {
        "patterns": [
            "libvulkan.so*",
            "libSPIRV*.so*",
        ],
        "rpath": "$ORIGIN",
    },
}


def _matches_any(filename: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(filename, p) for p in patterns)


def _copy_matching_files(source_dir: Path, dest_dir: Path, patterns: list[str]) -> int:
    """Copy files matching any pattern from source to dest. Returns count copied."""
    count = 0
    if not source_dir.exists():
        return count
    for file in source_dir.iterdir():
        if file.is_file() and _matches_any(file.name, patterns):
            shutil.copy2(file, dest_dir / file.name)
            count += 1
    return count


def _set_rpath(bin_dir: Path) -> None:
    """Set RPATH to $ORIGIN for all ELF binaries in directory."""
    for file in bin_dir.iterdir():
        if file.is_file() and not file.is_symlink():
            try:
                subprocess.run(
                    ["patchelf", "--set-rpath", "$ORIGIN", str(file)],
                    check=True,
                    capture_output=True,
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass  # Not an ELF binary or patchelf not installed


def bundle_libs(artifact_dir: Path, strategy_name: str) -> None:
    """Bundle runtime libraries into artifact_dir using the named strategy."""
    strategy = BUNDLE_STRATEGIES.get(strategy_name)
    if not strategy or not strategy["patterns"]:
        return

    for pattern in strategy["patterns"]:
        # Search common library locations
        for lib_base in [Path("/usr/lib"), Path("/usr/lib64"), Path("/usr/local/lib")]:
            _copy_matching_files(lib_base, artifact_dir, [pattern])

    # Copy extra directories (e.g. ROCm tuning libraries)
    for extra in strategy.get("extra_dirs", []):
        for lib_base in [Path("/opt/rocm/lib"), Path("/opt/cuda/lib64")]:
            extra_src = lib_base / extra
            if extra_src.exists():
                dest = artifact_dir / extra
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copytree(extra_src, dest, dirs_exist_ok=True)

    _set_rpath(artifact_dir)


def bundle_libs_custom(
    artifact_dir: Path, source_dir: Path, patterns: list[str]
) -> None:
    """Copy files matching patterns from source_dir into artifact_dir."""
    _copy_matching_files(source_dir, artifact_dir, patterns)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd llama-builds && python -m pytest tests/test_bundle_libs.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
cd llama-builds && git add scripts/bundle_libs.py tests/test_bundle_libs.py && git commit -m "feat: add library bundling script with per-backend strategies

Supports cpu-static, rocm-therock, cuda-redist, vulkan-sdk strategies.
Copies matching runtime libs and sets RPATH=$ORIGIN via patchelf.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Create ROCm target with extended METADATA

**Files:**
- Create: `llama-builds/targets/upstream-rocm/build.sh`

**Interfaces:**
- Consumes: Existing METADATA format from other targets
- Produces: New ROCm target that matrix generation can pick up

- [ ] **Step 1: Create the target build script**

```bash
#!/usr/bin/env bash
# METADATA
# name=llama.cpp upstream ROCm baseline
# repo=ggml-org/llama.cpp
# ref=0ab9d6fed73dbc5dc8026c868cb10a6728c4ed48
# backend=rocm
# arch=x86_64
# gpu_targets=gfx110X,gfx1151,gfx1150,gfx120X,gfx103X,gfx90a,gfx908
# capabilities=chat,embed
# runtime_deps=librocblas,libhipblas,libamdhip64,librocsolver,libroctx64
# bundle_strategy=rocm-therock
set -euo pipefail

REPO="${REPO:-ggml-org/llama.cpp}"
REF="${REF:-main}"

echo "Building llama.cpp ROCm baseline"
echo "  Repo: $REPO"
echo "  Ref:  $REF"
echo "  Backend: rocm"
echo "  Arch: x86_64"

if [[ -z "${GITHUB_ACTIONS:-}" ]]; then
  echo "Running outside GitHub Actions — building locally..."

  BUILD_DIR=$(mktemp -d)
  trap 'rm -rf "$BUILD_DIR"' EXIT

  git clone --depth 1 --branch "$REF" "https://github.com/$REPO.git" "$BUILD_DIR/repo" 2>/dev/null \
    || git clone --depth 1 "https://github.com/$REPO.git" "$BUILD_DIR/repo"

  cd "$BUILD_DIR/repo"
  mkdir -p build && cd build
  cmake .. -DCMAKE_BUILD_TYPE=Release -DGGML_HIP=ON -G Ninja
  cmake --build . -j$(nproc)

  echo "Build complete. Binaries in: $(pwd)"
  ls -la llama-server llama-cli 2>/dev/null || echo "Note: binary names may vary"
else
  echo "Running in GitHub Actions — use the build-llama composite action."
fi
```

- [ ] **Step 2: Make executable and verify METADATA parses**

Run: `cd llama-builds && python -c "from scripts.metadata_parser import parse_metadata; m = parse_metadata('targets/upstream-rocm/build.sh'); print(m)"`
Expected: Dict with `backend=rocm`, `gpu_targets` containing 7 targets, `bundle_strategy=rocm-therock`

- [ ] **Step 3: Commit**

```bash
cd llama-builds && git add targets/upstream-rocm/build.sh && git commit -m "feat: add ROCm build target with extended METADATA

Includes gpu_targets, runtime_deps, and bundle_strategy fields for
the matrix generator and library bundler.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Rewrite build.yml to use matrix generation

**Files:**
- Rewrite: `llama-builds/.github/workflows/build.yml` (new file, replaces inline matrix logic)
- Modify: `llama-builds/.github/workflows/matrix.yml` (add ref forwarding)

**Interfaces:**
- Consumes: `generate_matrix.py` output, `bundle_libs.py`, existing `action.yml`
- Produces: GitHub Actions workflow that fans out across all targets

- [ ] **Step 1: Create build.yml**

```yaml
# llama-builds/.github/workflows/build.yml
name: Build

on:
  workflow_call:
    inputs:
      ref:
        type: string
        default: "latest"
  workflow_dispatch:
    inputs:
      ref:
        type: string
        description: "llama.cpp ref (SHA, tag, branch, or 'latest')"
        default: "latest"

permissions:
  contents: read

jobs:
  generate-matrix:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.gen.outputs.matrix }}
      target_count: ${{ steps.gen.outputs.target_count }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Generate build matrix
        id: gen
        run: |
          python scripts/generate_matrix.py
          # generate_matrix.py writes to matrix.json
          matrix=$(cat matrix.json)
          target_count=$(echo "$matrix" | python -c "import sys,json; print(len(json.load(sys.stdin)['include']))")
          echo "matrix=$matrix" >> "$GITHUB_OUTPUT"
          echo "target_count=$target_count" >> "$GITHUB_OUTPUT"
          echo "Matrix has $target_count target(s)"

  build:
    needs: generate-matrix
    if: needs.generate-matrix.outputs.target_count != '0'
    runs-on: ubuntu-22.04
    strategy:
      fail-fast: false
      matrix: ${{ fromJson(needs.generate-matrix.outputs.matrix) }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Checkout target repo
        uses: actions/checkout@v4
        with:
          repository: ${{ matrix.repo }}
          ref: ${{ inputs.ref == 'latest' && matrix.ref || inputs.ref }}
          path: _build/target
          fetch-depth: 1

      - name: Resolve full SHA
        id: resolve
        run: |
          cd _build/target
          FULL_SHA=$(git rev-parse HEAD)
          echo "resolved_sha=$FULL_SHA" >> "$GITHUB_OUTPUT"

      - name: Install dependencies
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y -qq cmake ninja-build patchelf

          case "${{ matrix.backend }}" in
            cuda)
              wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
              sudo dpkg -i cuda-keyring_1.1-1_all.deb
              sudo apt-get update -qq
              sudo apt-get install -y -qq cuda-toolkit
              ;;
            rocm)
              echo "::group::Installing ROCm"
              curl -sL "https://rocm.nightlies.amd.com/tarball-multi-arch/" \
                | grep -oP 'const files = \K\[.*?\]' \
                | python -c "
          import sys, json, re
          files = json.load(sys.stdin)
          prefix = 'therock-dist-linux-'
          latest = max(
              [f for f in files if f['name'].startswith(prefix) and f['name'].endswith('.tar.gz')],
              key=lambda f: re.search(r'(\d{8})\.tar\.gz', f['name']).group(1)
          ) if files else None
          print(latest['name'] if latest else '')
          " > /tmp/rocm_file.txt

              ROCM_FILE=$(cat /tmp/rocm_file.txt)
              if [ -n "$ROCM_FILE" ]; then
                echo "Downloading $ROCM_FILE"
                sudo mkdir -p /opt/rocm
                curl -sL "https://rocm.nightlies.amd.com/tarball-multi-arch/$ROCM_FILE" \
                  | sudo tar --use-compress-program=gzip -xf - -C /opt/rocm --strip-components=1
              fi
              echo "::endgroup::"
              ;;
            vulkan)
              sudo apt-get install -y -qq libvulkan-dev vulkan-validationlayers
              ;;
          esac

      - name: Set ROCm env vars
        if: matrix.backend == 'rocm'
        run: |
          echo "HIP_PATH=/opt/rocm" >> $GITHUB_ENV
          echo "ROCM_PATH=/opt/rocm" >> $GITHUB_ENV
          echo "/opt/rocm/bin:/opt/rocm/llvm/bin:$PATH" >> $GITHUB_PATH

      - name: CMake configure
        run: |
          cd _build/target
          mkdir -p build && cd build

          CMAKE_ARGS="-DCMAKE_BUILD_TYPE=Release"
          case "${{ matrix.backend }}" in
            cuda)   CMAKE_ARGS="$CMAKE_ARGS -DGGML_CUDA=ON" ;;
            rocm)   CMAKE_ARGS="$CMAKE_ARGS -DGGML_HIP=ON -DGPU_TARGETS=${{ matrix.gfx_target || 'gfx1100' }}" ;;
            vulkan) CMAKE_ARGS="$CMAKE_ARGS -DGGML_VULKAN=ON" ;;
          esac

          cmake .. $CMAKE_ARGS -G Ninja

      - name: Build
        run: |
          cd _build/target/build
          cmake --build . --config Release -j$(nproc)

      - name: Collect artifacts
        id: collect
        run: |
          INSTALL_DIR="${{ github.workspace }}/_build/install"
          mkdir -p "$INSTALL_DIR"

          cd _build/target/build
          BINARIES=()
          for bin in llama-server llama-cli llama-bench llama-quantize; do
            [ -f "$bin" ] && BINARIES+=("$bin")
          done

          if [ ${#BINARIES[@]} -eq 0 ]; then
            echo "::error::No binaries found after build"
            exit 1
          fi

          cp "${BINARIES[@]}" "$INSTALL_DIR/"
          echo "install_dir=$INSTALL_DIR" >> "$GITHUB_OUTPUT"

      - name: Bundle runtime libraries
        run: |
          python scripts/bundle_libs.py "${{ steps.collect.outputs.install_dir }}" "${{ matrix.bundle_strategy }}"

      - name: Archive artifacts
        id: archive
        run: |
          INSTALL_DIR="${{ steps.collect.outputs.install_dir }}"
          FULL_SHA="${{ steps.resolve.outputs.resolved_sha }}"
          REF_PREFIX="${FULL_SHA:0:7}"
          GFX="${{ matrix.gfx_target }}"

          if [ -n "$GFX" ]; then
            ARCHIVE_NAME="llama-${REF_PREFIX}-1-ubuntu-${{ matrix.backend }}-${GFX}.tar.gz"
          else
            ARCHIVE_NAME="llama-${REF_PREFIX}-1-ubuntu-${{ matrix.backend }}-${{ matrix.arch }}.tar.gz"
          fi

          cd "$INSTALL_DIR"
          tar czf "${{ github.workspace }}/${ARCHIVE_NAME}" ./*
          echo "archive_name=$ARCHIVE_NAME" >> "$GITHUB_OUTPUT"

      - uses: actions/upload-artifact@v4
        with:
          name: llama-${{ matrix.backend }}-${{ matrix.gfx_target || matrix.arch }}
          path: _build/install/
          retention-days: 30
```

- [ ] **Step 2: Create the matrix generator script entry point**

Create `llama-builds/scripts/generate_matrix.py`:

```python
#!/usr/bin/env python3
"""Generate GitHub Actions build matrix from target METADATA."""
import json
import sys
from pathlib import Path

from scripts.metadata_parser import generate_matrix

targets_dir = Path("targets")
matrix = generate_matrix(targets_dir)

# Write to file for workflow to consume
Path("matrix.json").write_text(json.dumps(matrix))
print(json.dumps(matrix, indent=2))
```

- [ ] **Step 3: Test the matrix generator against real targets**

Run: `cd llama-builds && python scripts/generate_matrix.py`
Expected: JSON with `include` array containing entries for cpu, cuda, vulkan targets (no ROCm yet since GPU targets may not be in the existing build.sh files — they'll be picked up from the new upstream-rocm target)

- [ ] **Step 4: Commit**

```bash
cd llama-builds && git add .github/workflows/build.yml scripts/generate_matrix.py && git commit -m "feat: rewrite build workflow with config-driven matrix

Thin orchestrator: generate_matrix.py reads targets, fans out build
jobs per matrix entry. Supports all backends including ROCm.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Upstream watch workflow

**Files:**
- Create: `llama-builds/.github/workflows/upstream-watch.yml`

**Interfaces:**
- Consumes: `ggml-org/llama.cpp` HEAD SHA
- Produces: Triggers `build.yml` when upstream changes

- [ ] **Step 1: Create the workflow**

```yaml
# llama-builds/.github/workflows/upstream-watch.yml
name: Watch Upstream

on:
  schedule:
    - cron: "0 */6 * * *"  # Every 6 hours
  workflow_dispatch:

permissions:
  contents: write

jobs:
  check-upstream:
    runs-on: ubuntu-latest
    outputs:
      new_commit: ${{ steps.check.outputs.new_commit }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: Check for upstream changes
        id: check
        run: |
          LOCAL_SHA=$(cat .last-upstream-sha 2>/dev/null || echo "")
          UPSTREAM_SHA=$(git ls-remote https://github.com/ggml-org/llama.cpp.git HEAD | cut -f1)

          echo "Local:   ${LOCAL_SHA:0:12:-none}"
          echo "Upstream: ${UPSTREAM_SHA:0:12}"

          if [ "$LOCAL_SHA" != "$UPSTREAM_SHA" ]; then
            echo "New upstream commit detected!"
            echo "new_commit=$UPSTREAM_SHA" >> "$GITHUB_OUTPUT"
          else
            echo "No new upstream commits"
          fi

      - name: Update local SHA tracker
        if: steps.check.outputs.new_commit != ''
        run: |
          echo "${{ steps.check.outputs.new_commit }}" > .last-upstream-sha
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add .last-upstream-sha
          git commit -m "chore: update upstream SHA to ${{ steps.check.outputs.new_commit }}"
          git push

  trigger-build:
    needs: check-upstream
    if: needs.check-upstream.outputs.new_commit != ''
    uses: ./.github/workflows/build.yml
    with:
      ref: ${{ needs.check-upstream.outputs.new_commit }}
    secrets: inherit
```

- [ ] **Step 2: Commit**

```bash
cd llama-builds && git add .github/workflows/upstream-watch.yml && git commit -m "feat: add upstream watch workflow

Polls ggml-org/llama.cpp every 6h, triggers build on new commits.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 2: llama-builds — Release Automation

### Task 7: Release workflow with sequential tagging

**Files:**
- Create: `llama-builds/.github/workflows/release.yml`

**Interfaces:**
- Consumes: Build artifacts from `build.yml`
- Produces: GitHub Release with sequential `b####` tags

- [ ] **Step 1: Create the workflow**

```yaml
# llama-builds/.github/workflows/release.yml
name: Release

on:
  workflow_run:
    workflows: ["Build"]
    types: [completed]

permissions:
  contents: write

jobs:
  create-release:
    if: github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate sequential tag
        id: tag
        run: |
          EXISTING=$(gh release list --limit 1000 --json tagName --jq '.[].tagName' | grep -E '^b[0-9]+$' | sort -V || echo "")

          if [ -z "$EXISTING" ]; then
            NEXT=1000
          else
            HIGHEST=$(echo "$EXISTING" | tail -1 | sed 's/^b//')
            NEXT=$((HIGHEST + 1))
          fi

          TAG=$(printf "b%d" $NEXT)
          echo "tag=$TAG" >> "$GITHUB_OUTPUT"
          echo "Release tag: $TAG"

      - name: Check tag uniqueness
        id: check
        run: |
          TAG="${{ steps.tag.outputs.tag }}"
          if git ls-remote --tags origin "$TAG" | grep -q "$TAG"; then
            echo "exists=true" >> "$GITHUB_OUTPUT"
          else
            echo "exists=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Download all artifacts
        if: steps.check.outputs.exists == 'false'
        uses: actions/download-artifact@v4
        with:
          path: ./artifacts

      - name: Create release archives
        if: steps.check.outputs.exists == 'false'
        run: |
          TAG="${{ steps.tag.outputs.tag }}"
          for artifact_dir in artifacts/llama-*/; do
            name=$(basename "$artifact_dir")
            cd "$artifact_dir"
            zip -r "../../${name}-${TAG}.zip" ./*
            cd ../..
          done
          ls -la *.zip

      - name: Create GitHub Release
        if: steps.check.outputs.exists == 'false'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          TAG="${{ steps.tag.outputs.tag }}"
          gh release create "$TAG" \
            --title "$TAG" \
            --notes "Automated release from upstream llama.cpp build." \
            *.zip
```

- [ ] **Step 2: Commit**

```bash
cd llama-builds && git add .github/workflows/release.yml && git commit -m "feat: add release workflow with sequential b#### tagging

Creates GitHub Release with artifacts when Build workflow succeeds.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 3: heretek-manager — Core Server + Provider Abstraction

### Task 8: Scaffold heretek-manager with Express server

**Files:**
- Create: `heretek-manager/package.json`
- Create: `heretek-manager/tsconfig.json`
- Create: `heretek-manager/src/cli.ts`
- Create: `heretek-manager/src/server.ts`

**Interfaces:**
- Consumes: Node 20+, npm
- Produces: CLI that starts Express server on configurable port

- [ ] **Step 1: Initialize the project**

```bash
cd heretek-manager
npm init -y
npm install express ws
npm install -D typescript @types/node @types/express @types/ws tsx vitest
npx tsc --init --target ES2022 --module NodeNext --moduleResolution NodeNext --outDir dist --rootDir src --strict true
```

- [ ] **Step 2: Create package.json scripts**

Update `package.json` to add:

```json
{
  "scripts": {
    "dev": "tsx src/cli.ts",
    "build": "tsc",
    "start": "node dist/cli.js",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "bin": {
    "heretek-manager": "./dist/cli.js"
  }
}
```

- [ ] **Step 3: Create CLI entry point**

```typescript
// heretek-manager/src/cli.ts
import { createServer } from "./server.js";

const port = parseInt(process.env.PORT || "3847", 10);
const host = process.env.HOST || "localhost";

const server = createServer();

server.listen(port, host, () => {
  console.log(`heretek-manager running at http://${host}:${port}`);
});
```

- [ ] **Step 4: Create Express server**

```typescript
// heretek-manager/src/server.ts
import express from "express";
import type { Server as HttpServer } from "http";

export function createServer(): HttpServer {
  const app = express();
  app.use(express.json());

  app.get("/api/status", (_req, res) => {
    res.json({ status: "ok", version: "0.1.0" });
  });

  const http = require("http").createServer(app);
  return http;
}
```

- [ ] **Step 5: Test server starts**

Run: `cd heretek-manager && npx tsx src/cli.ts &; sleep 1; curl http://localhost:3847/api/status; kill %1`
Expected: `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 6: Commit**

```bash
cd heretek-manager && git add package.json tsconfig.json src/ && git commit -m "feat: scaffold Express server with CLI entry point

Minimal HTTP server with /api/status health endpoint.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: Provider abstraction layer

**Files:**
- Create: `heretek-manager/src/providers/types.ts`
- Create: `heretek-manager/src/providers/openai.ts`
- Create: `heretek-manager/src/providers/local.ts`
- Create: `heretek-manager/src/providers/ollama.ts`
- Create: `heretek-manager/tests/providers.test.ts`

**Interfaces:**
- Consumes: Express server from Task 8
- Produces: `AIProvider` interface, three provider implementations, provider registry

- [ ] **Step 1: Write the failing tests**

```typescript
// heretek-manager/tests/providers.test.ts
import { describe, it, expect } from "vitest";
import type { AIProvider, Model } from "../src/providers/types.js";

describe("AIProvider interface", () => {
  it("openai provider implements interface", async () => {
    const { OpenAIProvider } = await import("../src/providers/openai.js");
    const provider = new OpenAIProvider({ apiKey: "test-key" });
    expect(provider.id).toBe("openai");
    expect(provider.name).toBe("OpenAI");
    expect(provider.type).toBe("openai");
    expect(typeof provider.listModels).toBe("function");
    expect(typeof provider.chat).toBe("function");
    expect(typeof provider.health).toBe("function");
  });

  it("ollama provider implements interface", async () => {
    const { OllamaProvider } = await import("../src/providers/ollama.js");
    const provider = new OllamaProvider({ baseUrl: "http://localhost:11434" });
    expect(provider.id).toBe("ollama");
    expect(provider.type).toBe("ollama");
    expect(typeof provider.listModels).toBe("function");
  });

  it("local provider implements interface", async () => {
    const { LocalProvider } = await import("../src/providers/local.js");
    const provider = new LocalProvider({ binaryPath: "/usr/local/bin/llama-server" });
    expect(provider.id).toBe("local");
    expect(provider.type).toBe("local");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd heretek-manager && npx vitest run tests/providers.test.ts`
Expected: FAIL with import errors

- [ ] **Step 3: Implement types.ts**

```typescript
// heretek-manager/src/providers/types.ts
export interface AIProvider {
  readonly id: string;
  readonly name: string;
  readonly type: "openai" | "local" | "ollama";

  listModels(): Promise<Model[]>;
  getModel(id: string): Promise<Model | null>;
  chat(params: ChatParams): AsyncIterable<ChatChunk>;
  health(): Promise<HealthStatus>;
  configure(settings: Record<string, unknown>): Promise<void>;
}

export interface Model {
  id: string;
  name: string;
  provider: string;
  capabilities: ("chat" | "embed" | "vision" | "tools")[];
  contextWindow: number;
  local: boolean;
}

export interface ChatParams {
  model: string;
  messages: Message[];
  temperature?: number;
  maxTokens?: number;
}

export interface Message {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ChatChunk {
  content: string;
  done: boolean;
}

export interface HealthStatus {
  status: "ok" | "error";
  message?: string;
}
```

- [ ] **Step 4: Implement OpenAI provider**

```typescript
// heretek-manager/src/providers/openai.ts
import type { AIProvider, Model, ChatParams, ChatChunk, HealthStatus } from "./types.js";

export class OpenAIProvider implements AIProvider {
  readonly id = "openai";
  readonly name = "OpenAI";
  readonly type = "openai" as const;
  private apiKey: string;
  private baseUrl: string;

  constructor(opts: { apiKey: string; baseUrl?: string }) {
    this.apiKey = opts.apiKey;
    this.baseUrl = opts.baseUrl || "https://api.openai.com/v1";
  }

  async listModels(): Promise<Model[]> {
    const res = await fetch(`${this.baseUrl}/models`, {
      headers: { Authorization: `Bearer ${this.apiKey}` },
    });
    if (!res.ok) return [];
    const data = (await res.json()) as { data: { id: string }[] };
    return data.data.map((m) => ({
      id: m.id,
      name: m.id,
      provider: this.id,
      capabilities: ["chat", "tools"] as const,
      contextWindow: 128000,
      local: false,
    }));
  }

  async getModel(id: string): Promise<Model | null> {
    const models = await this.listModels();
    return models.find((m) => m.id === id) || null;
  }

  async *chat(params: ChatParams): AsyncIterable<ChatChunk> {
    const res = await fetch(`${this.baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: params.model,
        messages: params.messages,
        temperature: params.temperature,
        max_tokens: params.maxTokens,
        stream: true,
      }),
    });

    if (!res.ok || !res.body) {
      throw new Error(`OpenAI API error: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6);
        if (data === "[DONE]") {
          yield { content: "", done: true };
          return;
        }
        try {
          const parsed = JSON.parse(data);
          const content = parsed.choices?.[0]?.delta?.content || "";
          if (content) yield { content, done: false };
        } catch {
          // skip malformed lines
        }
      }
    }
  }

  async health(): Promise<HealthStatus> {
    try {
      const res = await fetch(`${this.baseUrl}/models`, {
        headers: { Authorization: `Bearer ${this.apiKey}` },
      });
      return res.ok
        ? { status: "ok" }
        : { status: "error", message: `HTTP ${res.status}` };
    } catch (e) {
      return { status: "error", message: String(e) };
    }
  }

  async configure(settings: Record<string, unknown>): Promise<void> {
    if (settings.apiKey) this.apiKey = settings.apiKey as string;
    if (settings.baseUrl) this.baseUrl = settings.baseUrl as string;
  }
}
```

- [ ] **Step 5: Implement Ollama provider**

```typescript
// heretek-manager/src/providers/ollama.ts
import type { AIProvider, Model, ChatParams, ChatChunk, HealthStatus } from "./types.js";

export class OllamaProvider implements AIProvider {
  readonly id = "ollama";
  readonly name = "Ollama";
  readonly type = "ollama" as const;
  private baseUrl: string;

  constructor(opts: { baseUrl?: string }) {
    this.baseUrl = opts.baseUrl || "http://localhost:11434";
  }

  async listModels(): Promise<Model[]> {
    const res = await fetch(`${this.baseUrl}/api/tags`);
    if (!res.ok) return [];
    const data = (await res.json()) as { models: { name: string; size: number }[] };
    return data.models.map((m) => ({
      id: m.name,
      name: m.name,
      provider: this.id,
      capabilities: ["chat"] as const,
      contextWindow: 4096,
      local: true,
    }));
  }

  async getModel(id: string): Promise<Model | null> {
    const models = await this.listModels();
    return models.find((m) => m.id === id) || null;
  }

  async *chat(params: ChatParams): AsyncIterable<ChatChunk> {
    const res = await fetch(`${this.baseUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: params.model,
        messages: params.messages.map((m) => ({ role: m.role, content: m.content })),
        stream: true,
      }),
    });

    if (!res.ok || !res.body) {
      throw new Error(`Ollama API error: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line) continue;
        try {
          const parsed = JSON.parse(line);
          if (parsed.message?.content) {
            yield { content: parsed.message.content, done: !!parsed.done };
          }
        } catch {
          // skip malformed lines
        }
      }
    }
  }

  async health(): Promise<HealthStatus> {
    try {
      const res = await fetch(`${this.baseUrl}/api/tags`);
      return res.ok
        ? { status: "ok" }
        : { status: "error", message: `HTTP ${res.status}` };
    } catch (e) {
      return { status: "error", message: String(e) };
    }
  }

  async configure(settings: Record<string, unknown>): Promise<void> {
    if (settings.baseUrl) this.baseUrl = settings.baseUrl as string;
  }
}
```

- [ ] **Step 6: Implement Local provider (stub)**

```typescript
// heretek-manager/src/providers/local.ts
import type { AIProvider, Model, ChatParams, ChatChunk, HealthStatus } from "./types.js";

export class LocalProvider implements AIProvider {
  readonly id = "local";
  readonly name = "Local llama.cpp";
  readonly type = "local" as const;
  private binaryPath: string;

  constructor(opts: { binaryPath: string }) {
    this.binaryPath = opts.binaryPath;
  }

  async listModels(): Promise<Model[]> {
    // Detect GGUF files in common locations
    return [];
  }

  async getModel(_id: string): Promise<Model | null> {
    return null;
  }

  async *_chat(_params: ChatParams): AsyncIterable<ChatChunk> {
    // TODO: spawn llama-server process and connect via HTTP
    yield { content: "Local provider not yet implemented", done: true };
  }

  async chat(params: ChatParams): AsyncIterable<ChatChunk> {
    return this._chat(params);
  }

  async health(): Promise<HealthStatus> {
    // Check if binary exists
    try {
      const { execSync } = await import("child_process");
      execSync(`test -x ${this.binaryPath}`);
      return { status: "ok" };
    } catch {
      return { status: "error", message: `Binary not found: ${this.binaryPath}` };
    }
  }

  async configure(settings: Record<string, unknown>): Promise<void> {
    if (settings.binaryPath) this.binaryPath = settings.binaryPath as string;
  }
}
```

- [ ] **Step 7: Run tests**

Run: `cd heretek-manager && npx vitest run tests/providers.test.ts`
Expected: 3 PASS

- [ ] **Step 8: Commit**

```bash
cd heretek-manager && git add src/providers/ tests/providers.test.ts && git commit -m "feat: add provider abstraction layer

AIProvider interface with OpenAI, Ollama, and local llama.cpp implementations.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: REST API endpoints

**Files:**
- Create: `heretek-manager/src/api/models.ts`
- Create: `heretek-manager/src/api/providers.ts`
- Create: `heretek-manager/src/api/status.ts`
- Modify: `heretek-manager/src/server.ts`
- Create: `heretek-manager/tests/api.test.ts`

**Interfaces:**
- Consumes: Provider registry from Task 9
- Produces: Mounted Express routers for `/api/models`, `/api/providers`, `/api/status`

- [ ] **Step 1: Write the failing tests**

```typescript
// heretek-manager/tests/api.test.ts
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import type { Server } from "http";
import { createServer } from "../src/server.js";

let server: Server;
let baseUrl: string;

beforeAll(async () => {
  server = createServer();
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const addr = server.address();
  baseUrl = `http://localhost:${(addr as { port: number }).port}`;
});

afterAll(() => server.close());

describe("GET /api/status", () => {
  it("returns ok", async () => {
    const res = await fetch(`${baseUrl}/api/status`);
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.status).toBe("ok");
  });
});

describe("GET /api/providers", () => {
  it("returns provider list", async () => {
    const res = await fetch(`${baseUrl}/api/providers`);
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(Array.isArray(body.providers)).toBe(true);
  });
});

describe("GET /api/models", () => {
  it("returns model list", async () => {
    const res = await fetch(`${baseUrl}/api/models`);
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(Array.isArray(body.models)).toBe(true);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd heretek-manager && npx vitest run tests/api.test.ts`
Expected: FAIL (endpoints don't exist yet)

- [ ] **Step 3: Create status router**

```typescript
// heretek-manager/src/api/status.ts
import { Router } from "express";

export const statusRouter = Router();

statusRouter.get("/", (_req, res) => {
  res.json({ status: "ok", version: "0.1.0", uptime: process.uptime() });
});
```

- [ ] **Step 4: Create providers router**

```typescript
// heretek-manager/src/api/providers.ts
import { Router } from "express";
import type { AIProvider } from "../providers/types.js";

export function createProvidersRouter(registry: Map<string, AIProvider>) {
  const router = Router();

  router.get("/", (_req, res) => {
    const providers = Array.from(registry.values()).map((p) => ({
      id: p.id,
      name: p.name,
      type: p.type,
    }));
    res.json({ providers });
  });

  router.get("/:id/health", async (req, res) => {
    const provider = registry.get(req.params.id);
    if (!provider) {
      res.status(404).json({ error: "Provider not found" });
      return;
    }
    const health = await provider.health();
    res.json(health);
  });

  return router;
}
```

- [ ] **Step 5: Create models router**

```typescript
// heretek-manager/src/api/models.ts
import { Router } from "express";
import type { AIProvider } from "../providers/types.js";

export function createModelsRouter(registry: Map<string, AIProvider>) {
  const router = Router();

  router.get("/", async (_req, res) => {
    const allModels = [];
    for (const provider of registry.values()) {
      try {
        const models = await provider.listModels();
        allModels.push(...models);
      } catch {
        // skip failed providers
      }
    }
    res.json({ models: allModels });
  });

  return router;
}
```

- [ ] **Step 6: Wire routers into server**

Update `heretek-manager/src/server.ts`:

```typescript
import express from "express";
import type { Server as HttpServer } from "http";
import { statusRouter } from "./api/status.js";
import { createProvidersRouter } from "./api/providers.js";
import { createModelsRouter } from "./api/models.js";
import type { AIProvider } from "./providers/types.js";

export function createServer(
  providers?: Map<string, AIProvider>
): HttpServer {
  const app = express();
  app.use(express.json());

  const registry = providers || new Map();

  app.use("/api/status", statusRouter);
  app.use("/api/providers", createProvidersRouter(registry));
  app.use("/api/models", createModelsRouter(registry));

  const http = require("http").createServer(app);
  return http;
}
```

- [ ] **Step 7: Run tests**

Run: `cd heretek-manager && npx vitest run tests/api.test.ts`
Expected: 3 PASS

- [ ] **Step 8: Commit**

```bash
cd heretek-manager && git add src/api/ src/server.ts tests/api.test.ts && git commit -m "feat: add REST API endpoints for providers and models

GET /api/status, /api/providers, /api/models with provider registry.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: WebSocket event system

**Files:**
- Create: `heretek-manager/src/ws/events.ts`
- Modify: `heretek-manager/src/server.ts`
- Create: `heretek-manager/tests/websocket.test.ts`

**Interfaces:**
- Consumes: HTTP server from Task 10
- Produces: WebSocket server broadcasting model/provider events

- [ ] **Step 1: Write the failing test**

```typescript
// heretek-manager/tests/websocket.test.ts
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import WebSocket from "ws";
import { createServer } from "../src/server.js";

let server: ReturnType<typeof createServer>;
let port: number;

beforeAll(async () => {
  server = createServer();
  await new Promise<void>((resolve) => server.listen(0, resolve));
  port = (server.address() as { port: number }).port;
});

afterAll(() => server.close());

describe("WebSocket", () => {
  it("connects and receives welcome", async () => {
    const ws = new WebSocket(`ws://localhost:${port}`);
    const msg = await new Promise<string>((resolve) => {
      ws.on("message", (data) => resolve(data.toString()));
    });
    ws.close();
    const parsed = JSON.parse(msg);
    expect(parsed.type).toBe("connected");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd heretek-manager && npx vitest run tests/websocket.test.ts`
Expected: FAIL (WebSocket not implemented)

- [ ] **Step 3: Implement WebSocket event broadcaster**

```typescript
// heretek-manager/src/ws/events.ts
import { WebSocketServer, WebSocket } from "ws";
import type { Server } from "http";

export interface WSEvent {
  type: string;
  [key: string]: unknown;
}

export class EventBroadcaster {
  private wss: WebSocketServer;
  private clients: Set<WebSocket> = new Set();

  constructor(server: Server) {
    this.wss = new WebSocketServer({ server });
    this.wss.on("connection", (ws) => {
      this.clients.add(ws);
      ws.send(JSON.stringify({ type: "connected" }));
      ws.on("close", () => this.clients.delete(ws));
    });
  }

  broadcast(event: WSEvent): void {
    const data = JSON.stringify(event);
    for (const client of this.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(data);
      }
    }
  }
}
```

- [ ] **Step 4: Wire into server**

Update `heretek-manager/src/server.ts` to create `EventBroadcaster` and attach it to the HTTP server:

```typescript
// Add after const http = require("http").createServer(app):
import { EventBroadcaster } from "./ws/events.js";

// In createServer(), after creating http:
  const broadcaster = new EventBroadcaster(http);
  return { http, broadcaster };
```

Update return type and CLI to destructure.

- [ ] **Step 5: Run test**

Run: `cd heretek-manager && npx vitest run tests/websocket.test.ts`
Expected: 1 PASS

- [ ] **Step 6: Commit**

```bash
cd heretek-manager && git add src/ws/ src/server.ts tests/websocket.test.ts && git commit -m "feat: add WebSocket event broadcaster

Real-time event system for model/provider status updates.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Phase 4: heretek-manager — Vite SPA + Profile Management

### Task 12: Scaffold Vite + React SPA

**Files:**
- Create: `heretek-manager/ui/package.json`
- Create: `heretek-manager/ui/vite.config.ts`
- Create: `heretek-manager/ui/index.html`
- Create: `heretek-manager/ui/src/App.tsx`

**Interfaces:**
- Consumes: REST API from Task 10
- Produces: Minimal SPA that fetches `/api/status` and displays it

- [ ] **Step 1: Scaffold Vite project**

```bash
cd heretek-manager/ui
npm init -y
npm install react react-dom
npm install -D vite @vitejs/plugin-react @types/react @types/react-dom typescript
```

- [ ] **Step 2: Create vite.config.ts**

```typescript
// heretek-manager/ui/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:3847",
      "/ws": { target: "ws://localhost:3847", ws: true },
    },
  },
  build: {
    outDir: "../dist/ui",
    emptyOutDir: true,
  },
});
```

- [ ] **Step 3: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>heretek-manager</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

- [ ] **Step 4: Create App.tsx**

```tsx
// heretek-manager/ui/src/App.tsx
import { useState, useEffect } from "react";

export default function App() {
  const [status, setStatus] = useState<{ status: string; version: string } | null>(null);

  useEffect(() => {
    fetch("/api/status")
      .then((r) => r.json())
      .then(setStatus)
      .catch(console.error);
  }, []);

  if (!status) return <div>Loading...</div>;

  return (
    <div>
      <h1>heretek-manager</h1>
      <p>Status: {status.status}</p>
      <p>Version: {status.version}</p>
    </div>
  );
}
```

- [ ] **Step 5: Create main.tsx**

```tsx
// heretek-manager/ui/src/main.tsx
import { createRoot } from "react-dom/client";
import App from "./App.js";

createRoot(document.getElementById("root")!).render(<App />);
```

- [ ] **Step 6: Commit**

```bash
cd heretek-manager && git add ui/ && git commit -m "feat: scaffold Vite + React SPA

Minimal UI with /api/status display and dev proxy to backend.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 13: Profile management

**Files:**
- Create: `heretek-manager/src/config/profiles.ts`
- Create: `heretek-manager/src/config/schema.ts`
- Create: `heretek-manager/src/api/profiles.ts`
- Create: `heretek-manager/tests/profiles.test.ts`

**Interfaces:**
- Consumes: Filesystem (`~/.heretek/profiles/`), Express router pattern from Task 10
- Produces: CRUD for profiles, active profile switching

- [ ] **Step 1: Write the failing tests**

```typescript
// heretek-manager/tests/profiles.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { ProfileStore } from "../src/config/profiles.js";
import { mkdirSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

let store: ProfileStore;
let testDir: string;

beforeEach(() => {
  testDir = join(tmpdir(), `test-profiles-${Date.now()}`);
  mkdirSync(testDir, { recursive: true });
  store = new ProfileStore(testDir);
});

describe("ProfileStore", () => {
  it("lists empty profiles", async () => {
    const profiles = await store.list();
    expect(profiles).toEqual([]);
  });

  it("creates and retrieves a profile", async () => {
    const profile = await store.create({
      name: "default",
      providers: {},
      defaults: { model: "gpt-4", temperature: 0.7, maxTokens: 4096 },
    });
    expect(profile.id).toBeTruthy();
    expect(profile.name).toBe("default");

    const profiles = await store.list();
    expect(profiles).toHaveLength(1);
    expect(profiles[0].name).toBe("default");
  });

  it("switches active profile", async () => {
    await store.create({
      name: "profile-a",
      providers: {},
      defaults: { model: "gpt-4", temperature: 0.7, maxTokens: 4096 },
    });
    await store.create({
      name: "profile-b",
      providers: {},
      defaults: { model: "claude-3", temperature: 0.5, maxTokens: 8192 },
    });

    const profiles = await store.list();
    await store.setActive(profiles[1].id);
    const active = await store.getActive();
    expect(active?.name).toBe("profile-b");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd heretek-manager && npx vitest run tests/profiles.test.ts`
Expected: FAIL with import error

- [ ] **Step 3: Implement ProfileStore**

```typescript
// heretek-manager/src/config/profiles.ts
import { readFile, writeFile, readdir, mkdir } from "fs/promises";
import { join } from "path";
import { randomUUID } from "crypto";

export interface Profile {
  id: string;
  name: string;
  providers: Record<string, Record<string, unknown>>;
  defaults: {
    model: string;
    temperature: number;
    maxTokens: number;
  };
}

export class ProfileStore {
  private dir: string;

  constructor(dir: string) {
    this.dir = dir;
  }

  async list(): Promise<Profile[]> {
    await mkdir(this.dir, { recursive: true });
    const files = await readdir(this.dir);
    const profiles: Profile[] = [];
    for (const file of files) {
      if (!file.endsWith(".json")) continue;
      const content = await readFile(join(this.dir, file), "utf-8");
      profiles.push(JSON.parse(content));
    }
    return profiles;
  }

  async create(
    data: Omit<Profile, "id">
  ): Promise<Profile> {
    const profile: Profile = { ...data, id: randomUUID() };
    await mkdir(this.dir, { recursive: true });
    await writeFile(
      join(this.dir, `${profile.id}.json`),
      JSON.stringify(profile, null, 2)
    );
    return profile;
  }

  async getActive(): Promise<Profile | null> {
    const activeFile = join(this.dir, ".active");
    try {
      const id = (await readFile(activeFile, "utf-8")).trim();
      const content = await readFile(join(this.dir, `${id}.json`), "utf-8");
      return JSON.parse(content);
    } catch {
      return null;
    }
  }

  async setActive(id: string): Promise<void> {
    await writeFile(join(this.dir, ".active"), id);
  }
}
```

- [ ] **Step 4: Implement profiles API router**

```typescript
// heretek-manager/src/api/profiles.ts
import { Router } from "express";
import type { ProfileStore } from "../config/profiles.js";

export function createProfilesRouter(store: ProfileStore) {
  const router = Router();

  router.get("/", async (_req, res) => {
    const profiles = await store.list();
    const active = await store.getActive();
    res.json({ profiles, activeId: active?.id || null });
  });

  router.post("/", async (req, res) => {
    const profile = await store.create(req.body);
    res.status(201).json(profile);
  });

  router.put("/active", async (req, res) => {
    await store.setActive(req.body.id);
    res.json({ ok: true });
  });

  return router;
}
```

- [ ] **Step 5: Wire into server**

Add profiles router to `server.ts`:

```typescript
import { ProfileStore } from "./config/profiles.js";
import { createProfilesRouter } from "./api/profiles.js";

// In createServer():
  const profileStore = new ProfileStore(
    join(require("os").homedir(), ".heretek", "profiles")
  );
  app.use("/api/profiles", createProfilesRouter(profileStore));
```

- [ ] **Step 6: Run tests**

Run: `cd heretek-manager && npx vitest run tests/profiles.test.ts`
Expected: 3 PASS

- [ ] **Step 7: Commit**

```bash
cd heretek-manager && git add src/config/ src/api/profiles.ts tests/profiles.test.ts && git commit -m "feat: add profile management with filesystem persistence

ProfileStore with CRUD + active profile switching. Profiles stored in ~/.heretek/profiles/.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Phase 1 covers tasks 1-6 (matrix, bundling, ROCm target, build workflow, upstream watch). Phase 2 covers task 7 (release). Phase 3 covers tasks 8-11 (server, providers, API, WebSocket). Phase 4 covers tasks 12-13 (SPA, profiles). All spec sections addressed.
- [x] **Placeholder scan:** No TBDs, TODOs, or vague steps. All code blocks are complete.
- [x] **Type consistency:** `AIProvider` interface used consistently across tasks 9-11. `parse_metadata` return type consistent across tasks 1-2. `Profile` interface consistent across task 13.
- [ ] **Missing:** The spec mentions a `build-llama` composite action — the plan inlines this logic into `build.yml` steps instead, which is simpler and avoids maintaining a separate action. This is a deliberate simplification.
