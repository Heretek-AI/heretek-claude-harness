import { describe, it, expect } from "vitest";
import { estimate, commandPreview, type ModelArch, type Inputs } from "../../src/core/vram/report.js";

describe("report", () => {
  const arch7B: ModelArch = {
    name: "Llama-2-7B", architecture: "llama",
    n_layer: 32, n_embd: 4096, n_head: 32, n_head_kv: 32,
    training_ctx: 4096, params: 7_000_000_000,
  };

  const inputs: Inputs = {
    quant: "Q4_K_M", n_ctx: 8192, cache_dtype: "f16", flash_attn: true,
    gpu_vram_gb: [24], safety_margin_pct: 5,
  };

  it("estimate returns valid breakdown", () => {
    const bd = estimate(arch7B, inputs);
    expect(bd.weights_bytes).toBeGreaterThan(0);
    expect(bd.kv_cache_bytes).toBeGreaterThan(0);
    expect(bd.total_bytes).toBeGreaterThan(0);
    expect(bd.warnings).toBeDefined();
  });

  it("estimate includes safety margin", () => {
    const bd = estimate(arch7B, inputs);
    expect(bd.safety_margin_bytes).toBeGreaterThan(0);
    expect(bd.total_bytes).toBeGreaterThan(bd.weights_bytes + bd.kv_cache_bytes);
  });

  it("commandPreview generates llama-server command", () => {
    const cmd = commandPreview(arch7B, inputs);
    expect(cmd).toContain("llama-server");
    expect(cmd).toContain("-ngl 999");
    expect(cmd).toContain("--flash-attn");
  });

  it("commandPreview includes YaRN flags when ctx > training", () => {
    const extendedInputs: Inputs = { ...inputs, n_ctx: 16384 };
    const cmd = commandPreview(arch7B, extendedInputs);
    expect(cmd).toContain("--rope-scaling yarn");
  });
});
