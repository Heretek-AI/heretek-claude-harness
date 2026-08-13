# Automated Builds & Local Web UI

**Date:** 2026-08-02
**Status:** Draft
**Supersedes:** N/A

## 1. Problem Statement

The Heretek AI harness has two child repos that need production-grade build and distribution infrastructure:

- **llama-builds** has a GitHub Action for building llama.cpp forks, but builds are manual, single-target, and produce source-only artifacts. There is no automated upstream tracking, no nightly builds, no self-contained distributions (bundled runtime libraries), and no release automation.

- **heretek-manager** is a bare scaffold with no UI or runtime logic. It needs a local web interface for managing AI models, providers, and configurations.

This spec designs both systems in parallel, drawing on patterns from `lemonade-sdk/llamacpp-rocm` (automated multi-target builds with self-contained distributions) and `qwersyk/Newelle` (extension architecture, provider abstraction, MCP integration).

## 2. Goals

### llama-builds

1. **Automatic builds** triggered by upstream llama.cpp changes (not just manual dispatch)
2. **Full self-contained distributions** for all four backends: CPU, CUDA, ROCm, Vulkan
3. **Config-driven target matrix** — adding a backend = adding a YAML file
4. **Release automation** with sequential tagging and GitHub Releases
5. **Library bundling** — ship all runtime dependencies (ROCm `.so`, CUDA `.dll`, etc.) alongside binaries

### heretek-manager

1. **Local web UI** served by the Node CLI (Express + bundled SPA)
2. **Provider abstraction** supporting OpenAI API, local llama.cpp, and Ollama
3. **REST API + WebSocket** for model management and real-time status
4. **Settings management** with profile isolation (inspired by Newelle's profile system)

## 3. Architecture

### 3.1 llama-builds: Config-Driven Build Matrix

```
targets/
├── _template/           # existing
├── upstream-cpu/        # existing — METADATA header defines build params
├── upstream-cuda/       # existing
├── upstream-vulkan/     # existing
└── upstream-rocm/       # new — ROCm backend target

scripts/
├── generate_matrix.py   # NEW — reads targets/*/METADATA → GitHub Actions matrix JSON
├── bundle_libs.py       # NEW — copies runtime libs into artifact dir, sets RPATH
└── ...existing...

.github/workflows/
├── build.yml            # REWRITE — thin workflow calling generate_matrix, then matrix fan-out
├── release.yml          # NEW — sequential tagging + GitHub Release creation
└── upstream-watch.yml   # NEW — polls upstream llama.cpp for new commits, triggers build.yml
```

#### Target METADATA format (extended)

Existing targets already have METADATA headers in `build.sh`. Extend the format:

```bash
# METADATA
# name=llama.cpp upstream ROCm baseline
# repo=ggml-org/llama.cpp
# ref=0ab9d6fed73dbc5dc8026c868cb10a6728c4ed48
# backend=rocm
# arch=x86_64
# gpu_targets=gfx1100,gfx1101,gfx1102,gfx1103
# capabilities=chat,embed
# runtime_deps=librocblas,libhipblas,libamdhip64,librocsolver,libroctx64
# bundle_strategy=rocm-therock   # NEW — how to gather runtime libs
```

New METADATA fields:
- `gpu_targets` — comma-separated GPU ISA targets (for ROCm/CUDA family mapping)
- `runtime_deps` — comma-separated library basenames to bundle
- `bundle_strategy` — which bundling logic to apply (`rocm-therock`, `cuda-redist`, `vulkan-sdk`, `cpu-static`)

#### generate_matrix.py

Reads all `targets/*/build.sh` METADATA headers and emits GitHub Actions matrix JSON:

```python
# Pseudocode
def generate_matrix(targets_dir: Path) -> dict:
    targets = []
    for build_sh in sorted(targets_dir.glob("*/build.sh")):
        meta = parse_metadata(build_sh)
        if meta["backend"] == "rocm":
            # Expand GPU family targets to individual ISAs
            for family in meta["gpu_targets"].split(","):
                for isa in expand_gpu_family(family):
                    targets.append({
                        "target": meta["name"],
                        "backend": "rocm",
                        "gfx_target": isa,
                        "repo": meta["repo"],
                        "ref": meta["ref"],
                        "bundle_strategy": meta["bundle_strategy"],
                    })
        else:
            targets.append({
                "target": meta["name"],
                "backend": meta["backend"],
                "repo": meta["repo"],
                "ref": meta["ref"],
                "bundle_strategy": meta["bundle_strategy"],
            })
    return {"include": targets}
```

Emits to `$GITHUB_OUTPUT` as `matrix` JSON.

#### bundle_libs.py

Modeled after llamacpp-rocm's library copying pattern but generalized per `bundle_strategy`:

```python
BUNDLE_STRATEGIES = {
    "rocm-therock": {
        "source_dir": "/opt/rocm/lib",
        "patterns": ["librocblas.so*", "libhipblas.so*", "libamdhip64.so*", ...],
        "rpath": "$ORIGIN",
        "extra_dirs": ["rocblas/library", "hipblaslt/library"],
    },
    "cuda-redist": {
        "source_dir": "/usr/local/cuda/lib64",
        "patterns": ["libcublas.so*", "libcudart.so*", "libcufft.so*", ...],
        "rpath": "$ORIGIN",
    },
    "vulkan-sdk": {
        "source_dir": "/usr/lib/x86_64-linux-gnu",
        "patterns": ["libvulkan.so*", "libSPIRV*.so*"],
        "rpath": "$ORIGIN",
    },
    "cpu-static": {
        # No runtime deps to bundle — statically linked
        "patterns": [],
    },
}
```

On Linux: `patchelf --set-rpath '$ORIGIN'` for each binary.
On Windows: DLLs placed alongside `.exe` (no RPATH equivalent needed).

#### Upstream Watch

`upstream-watch.yml` — polls `ggml-org/llama.cpp` for new commits on `master`:

```yaml
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  check-upstream:
    runs-on: ubuntu-latest
    outputs:
      new_commit: ${{ steps.check.outputs.new_commit }}
    steps:
      - id: check
        run: |
          LOCAL_SHA=$(cat .last-upstream-sha 2>/dev/null || echo "")
          UPSTREAM_SHA=$(git ls-remote https://github.com/ggml-org/llama.cpp.git HEAD | cut -f1)
          if [ "$LOCAL_SHA" != "$UPSTREAM_SHA" ]; then
            echo "new_commit=$UPSTREAM_SHA" >> $GITHUB_OUTPUT
            echo "$UPSTREAM_SHA" > .last-upstream-sha
          fi

  trigger-build:
    needs: check-upstream
    if: needs.check-upstream.outputs.new_commit != ''
    uses: ./.github/workflows/build.yml
    with:
      ref: ${{ needs.check-upstream.outputs.new_commit }}
```

#### build.yml (rewritten)

Thin orchestrator:

```yaml
on:
  workflow_call:
    inputs:
      ref:
        type: string
        default: 'latest'
  workflow_dispatch:
    inputs:
      ref:
        type: string
        default: 'latest'

jobs:
  generate-matrix:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.gen.outputs.matrix }}
    steps:
      - uses: actions/checkout@v4
      - id: gen
        run: python scripts/generate_matrix.py >> $GITHUB_OUTPUT

  build:
    needs: generate-matrix
    strategy:
      matrix: ${{ fromJson(needs.generate-matrix.outputs.matrix) }}
      fail-fast: false
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/build-llama
        with:
          repo: ${{ matrix.repo }}
          ref: ${{ inputs.ref }}
          backend: ${{ matrix.backend }}
          gfx_target: ${{ matrix.gfx_target || '' }}
      - uses: ./.github/actions/bundle-libs
        with:
          strategy: ${{ matrix.bundle_strategy }}
      - uses: actions/upload-artifact@v4
        with:
          name: llama-${{ matrix.backend }}-${{ matrix.gfx_target || 'x64' }}
          path: build/bin/
```

### 3.2 heretek-manager: Local Web UI

```
heretek-manager/
├── src/
│   ├── cli.ts              # CLI entry point (commander.js)
│   ├── server.ts           # Express/Fastify server
│   ├── api/                # REST endpoints
│   │   ├── models.ts       # GET/POST /api/models
│   │   ├── providers.ts    # GET/POST /api/providers
│   │   ├── config.ts       # GET/PUT /api/config
│   │   └── status.ts       # GET /api/status
│   ├── ws/                 # WebSocket handlers
│   │   └── events.ts       # Real-time status updates
│   ├── providers/          # Provider abstraction layer
│   │   ├── types.ts        # Common interface
│   │   ├── openai.ts       # OpenAI API provider
│   │   ├── local.ts        # Local llama.cpp provider
│   │   └── ollama.ts       # Ollama provider
│   └── config/             # Settings management
│       ├── profiles.ts     # Profile isolation (à la Newelle)
│       └── schema.ts       # Config schema validation
├── ui/                     # SPA source (Vite + framework)
│   ├── index.html
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   └── api/            # API client
│   └── vite.config.ts
├── package.json
└── tsconfig.json
```

#### Provider Abstraction (ported from Newelle)

Newelle's model interface maps cleanly to a TypeScript version:

```typescript
// src/providers/types.ts
interface AIProvider {
  id: string;
  name: string;
  type: 'openai' | 'local' | 'ollama';

  // Discovery
  listModels(): Promise<Model[]>;
  getModel(id: string): Promise<Model | null>;

  // Inference
  chat(params: ChatParams): AsyncIterable<ChatChunk>;
  embed(text: string): Promise<number[]>;

  // Lifecycle
  health(): Promise<HealthStatus>;
  configure(settings: ProviderSettings): Promise<void>;
}

interface Model {
  id: string;
  name: string;
  provider: string;
  capabilities: ('chat' | 'embed' | 'vision' | 'tools')[];
  contextWindow: number;
  local: boolean;
}

interface ChatParams {
  model: string;
  messages: Message[];
  tools?: Tool[];
  temperature?: number;
  maxTokens?: number;
}
```

#### REST API

```
GET    /api/status              — server health, running providers
GET    /api/models              — list all available models across providers
POST   /api/models/download     — download a model (for local provider)
GET    /api/providers           — list configured providers
POST   /api/providers           — add a provider (OpenAI key, Ollama URL, etc.)
PUT    /api/providers/:id       — update provider settings
DELETE /api/providers/:id       — remove a provider
GET    /api/config              — current configuration
PUT    /api/config              — update configuration
GET    /api/profiles            — list profiles
POST   /api/profiles            — create profile
PUT    /api/profiles/:id        — switch active profile
```

#### WebSocket Events

```
{ type: "model:loading",    model: string, progress: number }
{ type: "model:ready",      model: string }
{ type: "model:error",      model: string, error: string }
{ type: "provider:status",  provider: string, status: "ok" | "error" }
{ type: "build:progress",   target: string, step: string, progress: number }
```

#### Profile Management (from Newelle)

Newelle's profile system isolates settings per chat. We adapt this for model/provider configs:

```typescript
interface Profile {
  id: string;
  name: string;
  providers: Record<string, ProviderSettings>;
  defaults: {
    model: string;
    temperature: number;
    maxTokens: number;
  };
}
```

Profiles stored in `~/.heretek/profiles/`. Active profile selected via CLI flag or UI.

## 4. Data Flow

### llama-builds build pipeline

```
upstream-watch.yml (polls every 6h)
  └─ detects new llama.cpp commit
       └─ triggers build.yml with new SHA
            └─ generate_matrix.py reads targets/*/build.sh
                 └─ emits matrix JSON (CPU×1 + CUDA×1 + ROCm×7 + Vulkan×1 = 10 jobs)
                      └─ build job per matrix entry
                           ├─ clone upstream at SHA
                           ├─ cmake configure with backend-specific flags
                           ├─ cmake --build
                           ├─ bundle_libs.py copies runtime deps
                           ├─ patchelf RPATH (Linux)
                           └─ upload artifact
                                └─ release.yml aggregates artifacts
                                     ├─ generates b#### tag
                                     └─ creates GitHub Release with zips
```

### heretek-manager request flow

```
Browser ←→ Express server ←→ Provider layer ←→ External APIs
   │           │                  │
   │    REST + WebSocket    AIProvider interface
   │           │                  │
   │    /api/models         OpenAI API
   │    /api/providers      llama.cpp (local)
   │    /api/config         Ollama
   │    /api/status
   │
   └── SPA (Vite bundle served from memory)
```

## 5. Error Handling

### llama-builds

- **Upstream clone failure:** Retry 3× with exponential backoff. If all fail, create GitHub Issue with `upstream-sync-failure` label.
- **Build failure:** Upload partial artifacts for debugging. Mark matrix entry as failed but continue other entries (`fail-fast: false`).
- **Library bundling failure:** Warn but don't fail the build (some backends may not need bundled libs).
- **Release tag collision:** Check existing tags before creating. If `b####` exists, increment.

### heretek-manager

- **Provider connection failure:** Return structured error from `/api/providers/:id`. UI shows provider status as "disconnected" with retry button.
- **Model download failure:** Resume from checkpoint. WebSocket emits progress events.
- **Server startup failure:** If port in use, try next port. Print URL to stdout.

## 6. Testing Strategy

### llama-builds

- **generate_matrix.py:** Unit tests parsing METADATA headers, expanding GPU families, validating output JSON against GitHub Actions schema.
- **bundle_libs.py:** Unit tests for each bundle strategy (mock filesystem). Integration test verifying RPATH set correctly.
- **End-to-end:** CI workflow builds CPU target on every PR (fast, ~5 min). Full matrix build on nightly.

### heretek-manager

- **Provider abstraction:** Unit tests with mock HTTP for each provider (OpenAI, local, Ollama).
- **REST API:** Integration tests using supertest against Express app.
- **WebSocket:** Integration tests verifying event emission on model load/status changes.
- **UI:** Component tests with Vitest + Testing Library.

## 7. Migration / Rollout

### Phase 1: llama-builds (Week 1-2)
1. Add `generate_matrix.py` + tests
2. Add `bundle_libs.py` with `cpu-static` strategy
3. Rewrite `build.yml` to use matrix generation
4. Add `upstream-watch.yml` for polling
5. Add CPU self-contained distribution

### Phase 2: llama-builds backends (Week 3-4)
1. Add CUDA bundle strategy + test
2. Add ROCm bundle strategy (port from llamacpp-rocm patterns)
3. Add Vulkan bundle strategy
4. Add `release.yml` with sequential tagging

### Phase 3: heretek-manager core (Week 5-6)
1. Scaffold Express server + CLI entry point
2. Implement provider abstraction + OpenAI provider
3. Add REST API endpoints
4. Add WebSocket event system

### Phase 4: heretek-manager UI (Week 7-8)
1. Scaffold Vite + React/Svelte SPA
2. Implement model list, provider config, settings pages
3. Add real-time status via WebSocket
4. Profile management

## 8. Open Questions

- **Upstream polling vs webhook:** Polling is simpler but has latency. A GitHub webhook from upstream would be instant but requires upstream cooperation. Recommendation: start with polling (every 6h), add webhook support later.
- **UI framework:** React vs Svelte vs vanilla? The spec is framework-agnostic — the API contract is the key interface.
- **Model download UI:** Should heretek-manager handle model downloads (like Newelle does), or assume models are pre-installed? Recommendation: support both — detect local models, offer download for remote.
- **Windows builds for llama-builds:** llamacpp-rocm does Windows + Ubuntu. Do we need Windows support from day one? Recommendation: start with Linux, add Windows in Phase 2.

## 9. References

- llamacpp-rocm build workflow: `lemonade-sdk/llamacpp-rocm/.github/workflows/build-llamacpp-rocm.yml`
- llamacpp-rocm library bundling: `lemonade-sdk/llamacpp-rocm/utils/gather_required_libs.py`
- Newelle Flatpak manifest: `qwersyk/Newelle/io.github.qwersyk.Newelle.json`
- Newelle Meson build: `qwersyk/Newelle/meson.build`
- Newelle extension system: `qwersyk/Newelle/modules/`
- Our existing action.yml: `llama-builds/action.yml`
- Our existing targets: `llama-builds/targets/`
