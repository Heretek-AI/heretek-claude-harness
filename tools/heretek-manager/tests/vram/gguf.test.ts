import { describe, it, expect } from "vitest";
import { parseHeaderBytes, metadataToArch } from "../../src/core/vram/gguf.js";
import { readFileSync } from "fs";
import { join } from "path";

describe("gguf parser", () => {
  const fixture = readFileSync(join(import.meta.dirname, "fixtures/minimal.gguf"));

  it("parses GGUF header bytes", () => {
    const meta = parseHeaderBytes(fixture);
    expect(meta["general.architecture"]).toBe("llama");
  });

  it("metadataToArch extracts architecture fields", () => {
    const meta = { "general.architecture": "llama", "llama.block_count": 32 };
    const arch = metadataToArch(meta);
    expect(arch.architecture).toBe("llama");
    expect(arch.n_layer).toBe(32);
  });

  it("metadataToArch defaults to 0 for missing fields", () => {
    const arch = metadataToArch({});
    expect(arch.n_layer).toBe(0);
    expect(arch.n_embd).toBe(0);
  });
});
