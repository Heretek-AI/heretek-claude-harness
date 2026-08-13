import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { loadConfig, saveConfig, DEFAULT_CONFIG } from "../src/core/config.js";
import { mkdtemp, rm } from "fs/promises";
import { join } from "path";
import { tmpdir } from "os";

describe("config", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "heretek-test-"));
  });

  afterEach(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  it("loadConfig returns defaults when no file exists", async () => {
    const config = await loadConfig(tmpDir);
    expect(config.defaultQuant).toBe(DEFAULT_CONFIG.defaultQuant);
    expect(config.safetyMarginPct).toBe(DEFAULT_CONFIG.safetyMarginPct);
  });

  it("saveConfig persists and loadConfig reads it", async () => {
    await saveConfig(tmpDir, { ...DEFAULT_CONFIG, defaultQuant: "Q8_0" });
    const config = await loadConfig(tmpDir);
    expect(config.defaultQuant).toBe("Q8_0");
  });

  it("loadConfig merges with defaults for partial files", async () => {
    const fs = await import("fs/promises");
    await fs.writeFile(join(tmpDir, "config.json"), JSON.stringify({ defaultQuant: "F16" }));
    const config = await loadConfig(tmpDir);
    expect(config.defaultQuant).toBe("F16");
    expect(config.safetyMarginPct).toBe(DEFAULT_CONFIG.safetyMarginPct);
  });
});
