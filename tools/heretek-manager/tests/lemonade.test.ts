import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { detectLemonade, setupLemonade } from "../src/core/lemonade.js";
import { mkdtemp, rm, mkdir, writeFile, readFile } from "fs/promises";
import { join } from "path";
import { tmpdir } from "os";

describe("lemonade", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "heretek-lemonade-"));
  });

  afterEach(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  it("detectLemonade returns null when no config exists", async () => {
    const result = await detectLemonade(tmpDir);
    expect(result).toBeNull();
  });

  it("detectLemonade finds config when it exists", async () => {
    await mkdir(join(tmpDir, ".cache/lemonade"), { recursive: true });
    await writeFile(join(tmpDir, ".cache/lemonade/config.json"), "{}");
    const result = await detectLemonade(join(tmpDir, ".cache/lemonade/config.json"));
    expect(result).not.toBeNull();
    expect(result?.detected).toBe(true);
  });

  it("setupLemonade writes cuda_bin path", async () => {
    const configDir = join(tmpDir, ".cache/lemonade");
    await mkdir(configDir, { recursive: true });
    const configPath = join(configDir, "config.json");
    await writeFile(configPath, JSON.stringify({ llamacpp: {} }));
    await mkdir(join(tmpDir, "store/upstream-cuda-b1234/bin"), { recursive: true });

    await setupLemonade(configPath, [{
      id: "upstream-cuda-b1234", backend: "cuda",
      binPath: join(tmpDir, "store/upstream-cuda-b1234/bin"),
    }]);

    const config = JSON.parse(await readFile(configPath, "utf-8"));
    expect(config.llamacpp.cuda_bin).toContain("upstream-cuda-b1234");
  });
});
