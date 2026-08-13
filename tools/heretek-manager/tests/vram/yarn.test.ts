import { describe, it, expect } from "vitest";
import { autoConfigureYarn, yarnCoherenceWarnings, extensionRatio } from "../../src/core/vram/yarn.js";

describe("yarn", () => {
  it("no extension needed when target <= training", () => {
    const config = autoConfigureYarn(4096, 4096);
    expect(config.scaling).toBe(false);
  });

  it("auto-configures rope_freq_scale for extension", () => {
    const config = autoConfigureYarn(4096, 8192);
    expect(config.scaling).toBe(true);
    expect(config.rope_freq_scale).toBeCloseTo(0.5, 4);
  });

  it("extension ratio is 1.0 when no extension", () => {
    expect(extensionRatio(4096, 4096)).toBe(1.0);
  });

  it("extension ratio is 2.0 for 2x extension", () => {
    expect(extensionRatio(4096, 8192)).toBe(2.0);
  });

  it("no warnings for <= 2x extension", () => {
    const warns = yarnCoherenceWarnings(4096, 8192);
    expect(warns).toHaveLength(0);
  });

  it("warning for > 2x extension", () => {
    const warns = yarnCoherenceWarnings(4096, 16384); // 4x
    expect(warns.length).toBeGreaterThan(0);
    expect(warns[0]).toContain("quality degradation");
  });

  it("strong warning for >= 8x extension", () => {
    const warns = yarnCoherenceWarnings(4096, 32768); // 8x
    expect(warns.some(w => w.includes("incoherent"))).toBe(true);
  });
});
