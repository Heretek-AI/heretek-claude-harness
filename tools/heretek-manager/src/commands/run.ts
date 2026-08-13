// src/commands/run.ts
import { Command } from "commander";
import { spawn } from "child_process";
import { homedir } from "os";
import { join } from "path";
import { detectHardware } from "../core/hardware.js";
import { getActiveSymlink } from "../core/symlinks.js";
import { loadConfig } from "../core/config.js";
import { estimate, commandPreview } from "../core/vram/index.js";
import type { ModelArch, Inputs } from "../core/vram/report.js";

export const runCommand = new Command("run")
  .description("Run a model with optimized llama-server flags")
  .argument("<model>", "Path to GGUF model file (local or HF repo/filename)")
  .option("--ctx <size>", "Context window size", "8192")
  .option("--port <port>", "Server port", "8080")
  .option("--gpus <ids>", "Comma-separated GPU indices (e.g., 0,1)")
  .option("--quant <quant>", "Override quantization format")
  .option("--dry-run", "Show command without executing")
  .action(async (model, opts) => {
    const baseDir = join(homedir(), ".heretek");

    // 1. Find binary
    const binary = await getActiveSymlink(join(baseDir, "bin"));
    if (!binary) {
      console.error("❌ No active build. Run `heretek-manager init` first.");
      process.exit(1);
    }

    // 2. Detect hardware
    const hw = await detectHardware();
    const gpuVram = hw.gpus.map(g => g.vramMb / 1024);

    // 3. Load config
    const config = await loadConfig(baseDir);

    // 4. Parse GGUF or use defaults
    const arch: ModelArch = {
      params: 7_000_000_000, n_layer: 32, n_embd: 4096,
      n_head: 32, n_head_kv: 32, training_ctx: 4096,
    };

    // 5. Build Inputs
    const gpuIndices = opts.gpus ? opts.gpus.split(",").map(Number) : undefined;
    const filteredGpuVram = gpuIndices ? gpuIndices.map((i: number) => gpuVram[i] ?? 0) : gpuVram;

    const inputs: Inputs = {
      quant: opts.quant || config.defaultQuant,
      n_ctx: parseInt(opts.ctx),
      cache_dtype: config.cacheDtype,
      flash_attn: config.flashAttn,
      gpu_vram_gb: filteredGpuVram.length > 0 ? filteredGpuVram : [24],
      safety_margin_pct: config.safetyMarginPct,
    };

    // 6. Estimate VRAM
    const breakdown = estimate(arch, inputs);
    if (!breakdown.gpu?.all_fit) {
      console.warn("⚠️  Model may not fit in VRAM. Consider lowering context or quant.");
    }

    // 7. Generate command
    const cmd = commandPreview(arch, inputs);
    console.log("\n📋 Command:\n" + cmd + "\n");

    if (opts.dryRun) {
      console.log("(dry run — not executing)");
      return;
    }

    // 8. Spawn process
    console.log(`🚀 Starting llama-server on port ${opts.port}...`);
    const args = ["-m", model, "-c", opts.ctx, "--port", opts.port, "-ngl", "999"];
    if (config.flashAttn) args.push("--flash-attn");

    const child = spawn(binary, args, { stdio: "inherit" });
    child.on("error", (err) => {
      console.error(`❌ Failed to start: ${err.message}`);
      process.exit(1);
    });
  });
