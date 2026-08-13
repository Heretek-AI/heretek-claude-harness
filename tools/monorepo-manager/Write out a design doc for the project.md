# **Software Design Document: Heretek AI Package Ecosystem**

**Project Name:** Heretek AI Inference Packaging System
**Repositories:** llama-builds (Automated Matrix Pipeline & Registry) | heretek-manager (NPM Client & WebUI)
**Author:** Principal Systems Architect

## **1\. Executive Summary & Architecture Overview**

The **Heretek AI Package System** is a modular, cross-platform distribution and runtime manager for the local LLM inference ecosystem. Because the open-source AI landscape is fractured across dozens of specialized llama.cpp forks (such as ik\_llama.cpp, CachyLLama, KVarN, and TurboQuant), building a single binary is insufficient.
This system operates on a dual-repository architecture:

> 1. **llama-builds (CI/CD Registry):** A GitHub-hosted builder that runs daily matrix builds across hardware targets (CUDA, ROCm, Vulkan, CPU), creates pre-compiled distribution bundles, and publishes a static manifest.json registry to GitHub Pages.
> 2. **heretek-manager (NPM Package & WebUI):** A local CLI/WebUI runtime delivered via Node.js (npx heretek-manager). It audits local host hardware, queries the online manifest.json registry, recommends the optimal backend binary for the detected hardware profile, and manages side-by-side binary versions via atomic symlinking.

                  \+-----------------------------------+
                  |   Heretek-AI / llama-builds       |
                  |  (GitHub Actions Daily Matrix)    |
                  \+-----------------+-----------------+
                                    |
            \+-----------------------+-----------------------+
            |                                               |
            v                                               v
   \[ GitHub Releases \]                             \[ GitHub Pages \]
(Tarballs / Zip Binaries)                          (manifest.json Registry)
            |                                               |
            \+-----------------------+-----------------------+
                                    |
                                    v
                  \+-----------------------------------+
                  |     npx heretek-manager           |
                  |   Local Express Server (9048)     |
                  \+-----------------+-----------------+
                                    |
          \+-------------------------+-------------------------+
          |                         |                         |
          v                         v                         v
\[ Hardware Auditor \]      \[ Version Store \]          \[ Symlink Switcher \]
(nvidia-smi/rocminfo)   (\~/.heretek/store/...)      (\~/.heretek/bin/...)

## **2\. Component 1: llama-builds (Automated CI/CD Registry)**

llama-builds acts as the single source of truth for downstream clients. It tracks upstream repositories, compiles target variations, releases compiled artifacts, and indexes them into a static JSON feed.

### **2.1 Repository Directory Structure**

Plaintext
llama-builds/
├── .github/
│   └── workflows/
│       ├── daily-upstream-check.yml   \# Triggers builds on upstream diffs/cron
│       └── build-matrix.yml           \# Cross-platform matrix builder
├── targets/
│   ├── llama.cpp/
│   │   └── build.sh                   \# Custom CMake overrides for upstream
│   ├── ik\_llama.cpp/
│   │   └── build.sh                   \# Trellis quants \+ FlashMLA flags
│   ├── llamacpp-rocm/
│   │   └── build.sh                   \# AMD ROCm compiler optimizations
│   └── turboquant/
│       └── build.sh                   \# WHT-rotated KV cache flags
├── scripts/
│   ├── generate\_manifest.py           \# Scrapes releases & outputs manifest.json
│   └── audit\_matrix.py                \# Pre-build validation
└── manifest.json                      \# Hosted on GitHub Pages

### **2.2 Compilation Matrix Strategy**

To prevent runtime Just-In-Time (JIT) overhead and fix performance bottlenecks on unique hardware:

| Hardware Backend | Target Arch Flags | Crucial Compiler Directives |
| :---- | :---- | :---- |
| **NVIDIA CUDA** | CMAKE\_CUDA\_ARCHITECTURES="86;89;90a" | \-DGGML\_CUDA=ON |
| **AMD ROCm** | AMDGPU\_TARGETS="gfx1030;gfx1100;gfx1151" | \-DGGML\_HIP=ON (Disable ROCWMMA\_FATTN on APU builds) |
| **Vulkan** | SPIR-V standard bytecode via glslc | \-DGGML\_VULKAN=ON |
| **CPU / Edge** | AVX2 / AVX512 / ARM NEON | \-DGGML\_BLAS=ON \-DGGML\_NATIVE=OFF |

### **2.3 manifest.json Registry Schema**

Published to \[https://heretek-ai.github.io/llama-builds/manifest.json\](https://heretek-ai.github.io/llama-builds/manifest.json).

JSON
{
  "version": "1.0.0",
  "generated\_at": "2026-08-01T00:00:00Z",
  "packages": \[
    {
      "id": "ik\_llama.cpp",
      "name": "ik\_llama.cpp (Trellis & FlashMLA Fork)",
      "upstream\_url": "https://github.com/ikawrakow/ik\_llama.cpp",
      "version": "b3420-ik",
      "features": \["trellis-quants", "flash-mla", "moe-tensor-merge"\],
      "builds": \[
        {
          "os": "linux",
          "arch": "x86\_64",
          "backend": "vulkan",
          "target\_gpu\_arch": "gfx1151",
          "recommended\_for": \["amd-apu", "unified-memory"\],
          "download\_url": "https://github.com/Heretek-AI/llama-builds/releases/download/v1.0.0/ik\_llama-vulkan-gfx1151.tar.gz",
          "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        },
        {
          "os": "linux",
          "arch": "x86\_64",
          "backend": "cuda",
          "target\_gpu\_arch": "sm\_89",
          "recommended\_for": \["nvidia-rtx-4000"\],
          "download\_url": "https://github.com/Heretek-AI/llama-builds/releases/download/v1.0.0/ik\_llama-cuda-sm89.tar.gz",
          "sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"
        }
      \]
    }
  \]
}

## **3\. Component 2: heretek-manager (NPM Package & WebUI)**

The client application is distributed via NPM (npm install \-g heretek-manager or npx heretek-manager). It runs a local HTTP control plane and WebUI server while directly interfacing with host OS system binaries.

### **3.1 Client Directory Structure**

Plaintext
heretek-manager/
├── bin/
│   └── heretek.js                     \# CLI Entry point (npx heretek-manager)
├── src/
│   ├── server/
│   │   ├── index.js                   \# Express/Fastify Server on Port 9048
│   │   ├── auditor/
│   │   │   ├── nvidia.js              \# Parses nvidia-smi CLI output
│   │   │   ├── amd.js                 \# Parses rocminfo CLI & /proc/cmdline
│   │   │   ├── vulkan.js              \# Parses vulkaninfo CLI output
│   │   │   └── engine.js              \# Hardware Recommendation Rules Engine
│   │   ├── manager/
│   │   │   ├── downloader.js          \# Package retriever & checksum verifier
│   │   │   └── symlink.js             \# Atomic symlink management (\~/.heretek)
│   │   └── api/
│   │       └── routes.js              \# REST Endpoints for WebUI
│   └── webui/                         \# Frontend Dashboard (HTML5/React/Vue)
│       ├── index.html
│       ├── App.jsx
│       └── components/
└── package.json

### **3.2 Hardware Auditor & Recommendation Engine**

The client backend shells out to system tools (nvidia-smi, rocminfo, vulkaninfo) via Node child\_process.execSync to build a hardware signature.

                   \+----------------------------------+
                   |     Hardware Audit Triggered     |
                   \+----------------+-----------------+
                                    |
          \+-------------------------+-------------------------+
          |                         |                         |
          v                         v                         v
 \[ Shell: nvidia-smi \]    \[ Shell: rocminfo \]     \[ Shell: vulkaninfo \]
    Extract CUDA Cap        Extract AMD Target        Check RADV Driver
          |                         |                         |
          \+-------------------------+-------------------------+
                                    |
                                    v
                   \+----------------------------------+
                   | Parse /proc/cmdline (Linux)      |
                   | Check: ttm.pages\_limit           |
                   \+----------------+-----------------+
                                    |
                                    v
                   \+----------------------------------+
                   |  Recommendation Engine Decision  |
                   \+----------------------------------+

#### **Key Rules Engine Logic:**

> 1. **AMD APU / Strix Halo Preference:** If an AMD APU (gfx1151) is detected, the engine prioritizes **Vulkan (RADV)** builds over native ROCm due to benchmark performance advantages in token generation.
> 2. **TTM Buffer Warning:** On Linux systems with integrated GPUs, the engine checks /proc/cmdline for ttm.pages\_limit. If missing or insufficient, the WebUI displays an actionable alert instructing the user to set ttm.pages\_limit=30720000 to expose up to 120GB system memory to the GPU.
> 3. **CUDA Compute Matching:** Matches detected CUDA Compute Capabilities (e.g., 8.9 \-\> sm\_89) to pre-compiled static builds to avoid runtime JIT lag.

### **3.3 Storage Layout & Atomic Symlink Management**

Installations are organized side-by-side inside the user's home directory (\~/.heretek/).

Plaintext
\~/.heretek/
├── bin/
│   └── llama-server \-\> \~/.heretek/store/ik\_llama.cpp/b3420-ik-vulkan/bin/llama-server
└── store/
    ├── llama.cpp/
    │   └── b3500-cuda/
    │       └── bin/
    │           └── llama-server
    └── ik\_llama.cpp/
        ├── b3420-vulkan/
        │   └── bin/
        │       └── llama-server
        └── b3420-cuda/
            └── bin/
                └── llama-server

#### **Atomic Symlink Swap (Node.js Implementation):**

JavaScript
import fs from 'fs';
import path from 'path';
import os from 'os';

export function makeActiveVersion(packageName, versionSlug) {
  const homeDir \= os.homedir();
  const binDir \= path.join(homeDir, '.heretek', 'bin');
  const targetBinaryPath \= path.join(
    homeDir,
    '.heretek',
    'store',
    packageName,
    versionSlug,
    'bin',
    'llama-server'
  );

  const symlinkPath \= path.join(binDir, 'llama-server');
  const tempSymlinkPath \= path.join(binDir, 'llama-server.tmp');

  if (\!fs.existsSync(binDir)) {
    fs.mkdirSync(binDir, { recursive: true });
  }

  // Create temporary symlink first to guarantee atomic swap
  if (fs.existsSync(tempSymlinkPath)) fs.unlinkSync(tempSymlinkPath);
  fs.symlinkSync(targetBinaryPath, tempSymlinkPath);

  // Atomic rename (replaces existing symlink without downtime)
  fs.renameSync(tempSymlinkPath, symlinkPath);
}

## **4\. WebUI & API Specifications**

When npx heretek-manager is executed, it starts an HTTP server listening on http://localhost:9048 and opens the user's default browser.

\+---------------------------------------------------------------------------------+
|  HERETEK AI PACKAGE MANAGER v1.0                     \[ System Status: OK \]       |
\+---------------------------------------------------------------------------------+
|  HARDWARE PROFILE DETECTED                                                       |
|  CPU: AMD Ryzen AI Max+ 395 (Strix Halo) | RAM: 128GB Unified                     |
|  GPU: AMD gfx1151 (RADV Vulkan)          | VRAM Access: 120GB (TTM Unlocked)   |
\+---------------------------------------------------------------------------------+
|  RECOMMENDED FOR YOUR SYSTEM                                                    |
|  \[★ Primary Choice\] ik\_llama.cpp (vulkan-gfx1151)                               |
|  Features: Trellis Quants, FlashMLA, MoE Tensor Merge                           |
|  \[ Install & Set Active \]                                                       |
\+---------------------------------------------------------------------------------+
|  INSTALLED PACKAGES (Side-by-Side Store)                                         |
|  \- ik\_llama.cpp (vulkan-gfx1151) \[ACTIVE\] \--------\> symlink: \~/.heretek/bin/   |
|  \- llama.cpp (upstream-b3500)   \[INACTIVE\] \-------\> \[ Make Active \] \[ Remove \] |
\+---------------------------------------------------------------------------------+

### **4.1 REST API Endpoints**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| GET | /api/hardware | Returns detected CPU, GPU, driver versions, and TTM flags. |
| GET | /api/registry | Fetches and returns remote manifest.json with client hardware recommendations. |
| GET | /api/installed | Lists locally installed packages in \~/.heretek/store/. |
| POST | /api/install | Downloads, verifies SHA256, and extracts binary payload. |
| POST | /api/activate | Atomically updates \~/.heretek/bin/llama-server symlink. |

## **5\. Execution & Rollout Plan**

> 1. **Phase 1 (llama-builds CI Setup):**
   * Configure GitHub Actions workflows for matrix builds across CUDA, ROCm, and Vulkan.
   * Write generate\_manifest.py script to update static JSON on GitHub Pages.
> 2. **Phase 2 (heretek-manager Core CLI):**
   * Implement system command parsing routines (nvidia-smi, rocminfo, vulkaninfo).
   * Implement binary downloader, SHA256 verifier, and symlink management module.
> 3. **Phase 3 (WebUI Dashboard):**
   * Build Express server on port 9048 with embedded WebUI interface.
   * Integrate system recommendations banner and one-click active version swapping.
