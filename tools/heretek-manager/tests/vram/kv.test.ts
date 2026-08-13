import { describe, it, expect } from "vitest";
import { kvCacheBytes, computeScratchBytes, cache_dtype_bytes } from "../../src/core/vram/kv.js";

describe("kv cache math", () => {
  it("cache_dtype_bytes returns correct values", () => {
    expect(cache_dtype_bytes("f16")).toBe(2.0);
    expect(cache_dtype_bytes("q4_0")).toBe(0.5);
    expect(cache_dtype_bytes("f32")).toBe(4.0);
  });

  it("kvCacheBytes for Llama 2 7B at 4096 ctx", () => {
    // n_layer=32, n_embd=4096, n_head=32, n_head_kv=32, n_ctx=4096, f16
    // head_dim = 4096/32 = 128
    // per_layer = 4096 * 2 * 32 * 128 * 2 = 67,108,864 bytes
    // total = 32 * 67,108,864 = 2,147,483,648 (~2 GiB)
    const kv = kvCacheBytes({
      n_layer: 32, n_embd: 4096, n_head: 32, n_head_kv: 32,
      n_ctx: 4096, cache_dtype: "f16",
    });
    expect(kv).toBeCloseTo(2_147_483_648, -4);
  });

  it("kvCacheBytes with MTP adds extra layers", () => {
    const base = kvCacheBytes({
      n_layer: 32, n_embd: 4096, n_head: 32, n_head_kv: 32,
      n_ctx: 4096, cache_dtype: "f16", n_mtp: 0,
    });
    const withMtp = kvCacheBytes({
      n_layer: 32, n_embd: 4096, n_head: 32, n_head_kv: 32,
      n_ctx: 4096, cache_dtype: "f16", n_mtp: 1,
    });
    // MTP adds one extra layer worth of KV
    expect(withMtp).toBeGreaterThan(base);
  });

  it("computeScratchBytes returns positive for valid inputs", () => {
    const scratch = computeScratchBytes({
      n_layer: 32, n_embd: 4096, n_head: 32, n_head_kv: 32,
      n_batch: 512, compute_dtype: "f16", cache_dtype: "f16",
    });
    expect(scratch).toBeGreaterThan(0);
  });
});
