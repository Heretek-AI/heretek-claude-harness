// tests/vram/draft.test.ts
import { describe, it, expect } from "vitest";
import { draftBytes, isWeightless, isWeighted, type DraftInputs } from "../../src/core/vram/draft.js";

describe("draft (speculative decoding)", () => {
  it("disabled when spec_type is none", () => {
    const result = draftBytes({
      draft: { spec_type: "none", params: 0, quant: "Q4_K_M", n_layer: 1, cache_dtype: "f16" },
      target_n_ctx: 4096, target_n_embd: 4096, target_n_head: 32, target_n_head_kv: 32,
    });
    expect(result.enabled).toBe(false);
  });

  it("weightless types have zero VRAM", () => {
    const result = draftBytes({
      draft: { spec_type: "ngram-simple", params: 0, quant: "Q4_K_M", n_layer: 1, cache_dtype: "f16" },
      target_n_ctx: 4096, target_n_embd: 4096, target_n_head: 32, target_n_head_kv: 32,
    });
    expect(result.enabled).toBe(true);
    expect(result.total_bytes).toBe(0);
  });

  it("weighted types have non-zero VRAM", () => {
    const result = draftBytes({
      draft: { spec_type: "draft-simple", params: 1_000_000_000, quant: "Q4_K_M", n_layer: 1, cache_dtype: "f16" },
      target_n_ctx: 4096, target_n_embd: 4096, target_n_head: 32, target_n_head_kv: 32,
    });
    expect(result.enabled).toBe(true);
    expect(result.total_bytes).toBeGreaterThan(0);
  });

  it("isWeightless identifies ngram types", () => {
    expect(isWeightless("ngram-simple")).toBe(true);
    expect(isWeightless("draft-simple")).toBe(false);
  });

  it("isWeighted identifies draft types", () => {
    expect(isWeighted("draft-simple")).toBe(true);
    expect(isWeighted("ngram-simple")).toBe(false);
  });
});
