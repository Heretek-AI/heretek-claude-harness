import { describe, it, expect } from "vitest";
import { QUANT_BPW, weightBytes, quantFromFilename } from "../../src/core/vram/quant.js";

describe("quant", () => {
  it("QUANT_BPW has expected entries", () => {
    expect(QUANT_BPW["Q4_K_M"]).toBe(4.84375);
    expect(QUANT_BPW["Q8_0"]).toBe(8.5);
    expect(QUANT_BPW["F16"]).toBe(16.0);
  });

  it("weightBytes calculates correctly", () => {
    // 7B params at Q4_K_M (4.84375 bpw): 7e9 * 4.84375 / 8 = ~4.24 GiB
    const bytes = weightBytes(7_000_000_000, "Q4_K_M");
    expect(bytes).toBeCloseTo(4_238_281_250, -5);
  });

  it("weightBytes throws on unknown quant", () => {
    expect(() => weightBytes(1000, "UNKNOWN")).toThrow("Unknown quant type");
  });

  it("quantFromFilename detects Q4_K_M", () => {
    expect(quantFromFilename("model-Q4_K_M.gguf")).toBe("Q4_K_M");
  });

  it("quantFromFilename detects Q8_0", () => {
    expect(quantFromFilename("Model-Q8_0.gguf")).toBe("Q8_0");
  });

  it("quantFromFilename returns null for no match", () => {
    expect(quantFromFilename("model.gguf")).toBeNull();
  });
});
