// tests/vram/gpu.test.ts
import { describe, it, expect } from "vitest";
import { gpuSplit, fitGpus, type GpuSpec } from "../../src/core/vram/gpu.js";

describe("gpu split", () => {
  const singleGpu: GpuSpec[] = [{ vram_gb: 24, name: "RTX 4090" }];

  it("single GPU fits small model", () => {
    const result = gpuSplit({
      gpu_specs: singleGpu,
      weights_bytes: 4e9, kv_bytes: 2e9, scratch_bytes: 0.3e9,
    });
    expect(result.all_fit).toBe(true);
    expect(result.assignments).toHaveLength(1);
  });

  it("single GPU does not fit oversized model", () => {
    const result = gpuSplit({
      gpu_specs: singleGpu,
      weights_bytes: 20e9, kv_bytes: 10e9, scratch_bytes: 1e9,
    });
    expect(result.all_fit).toBe(false);
  });

  it("two GPUs split proportionally", () => {
    const gpus: GpuSpec[] = [
      { vram_gb: 24, name: "GPU 0" },
      { vram_gb: 12, name: "GPU 1" },
    ];
    const result = gpuSplit({
      gpu_specs: gpus,
      weights_bytes: 12e9, kv_bytes: 6e9, scratch_bytes: 0.3e9,
    });
    expect(result.all_fit).toBe(true);
    expect(result.assignments).toHaveLength(2);
    const gpu0 = result.assignments[0];
    const gpu1 = result.assignments[1];
    expect(gpu0.weight_bytes).toBeGreaterThan(gpu1.weight_bytes);
  });

  it("split_mode none puts everything on main GPU", () => {
    const gpus: GpuSpec[] = [
      { vram_gb: 24, name: "GPU 0" },
      { vram_gb: 12, name: "GPU 1" },
    ];
    const result = gpuSplit({
      gpu_specs: gpus,
      weights_bytes: 4e9, kv_bytes: 2e9, scratch_bytes: 0.3e9,
      split_mode: "none", main_gpu: 0,
    });
    expect(result.assignments[0].weight_bytes).toBe(4e9);
    expect(result.assignments[1].weight_bytes).toBe(0);
  });

  it("fitGpus returns true when all fit", () => {
    const result = gpuSplit({
      gpu_specs: singleGpu,
      weights_bytes: 4e9, kv_bytes: 2e9,
    });
    expect(fitGpus(result)).toBe(true);
  });
});
