import { describe, it, expect } from "vitest";
import { maxContext, bestQuant, minGpuSetup } from "../../src/core/vram/autofit.js";

describe("autofit", () => {
  // Minimal ModelArch and Inputs types — these match report.ts types
  const arch7B = {
    n_layer: 32, n_embd: 4096, n_head: 32, n_head_kv: 32,
    training_ctx: 4096, params: 7_000_000_000,
  };

  const inputs24GB = {
    quant: "Q4_K_M", n_ctx: 8192, cache_dtype: "f16", flash_attn: true,
    gpu_vram_gb: [24], safety_margin_pct: 5,
  };

  it("maxContext finds a valid context", () => {
    const result = maxContext(arch7B, inputs24GB);
    expect(result.fits).toBe(true);
    expect(result.n_ctx).toBeGreaterThan(0);
  });

  it("bestQuant finds a fitting quant", () => {
    const result = bestQuant(arch7B, inputs24GB);
    expect(result.fits).toBe(true);
    expect(result.quant).toBeTruthy();
  });

  it("minGpuSetup finds minimum GPUs", () => {
    const result = minGpuSetup(arch7B, inputs24GB);
    expect(result.fits).toBe(true);
    expect(result.n_gpus).toBeGreaterThanOrEqual(1);
  });
});
