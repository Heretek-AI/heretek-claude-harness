import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { listBuilds, getActiveBuild, writeMeta, readMeta } from "../src/core/store.js";
import { mkdtemp, rm, mkdir, writeFile, symlink } from "fs/promises";
import { join } from "path";
import { tmpdir } from "os";

describe("store", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "heretek-store-"));
    await mkdir(join(tmpDir, "store"), { recursive: true });
    await mkdir(join(tmpDir, "bin"), { recursive: true });
  });

  afterEach(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  it("listBuilds returns empty when no builds", async () => {
    const builds = await listBuilds(join(tmpDir, "store"));
    expect(builds).toHaveLength(0);
  });

  it("listBuilds finds installed builds", async () => {
    const buildDir = join(tmpDir, "store", "upstream-cuda-b1234");
    await mkdir(buildDir, { recursive: true });
    await writeMeta(buildDir, {
      id: "upstream-cuda-b1234", target: "upstream-cuda", buildNum: 1234,
      upstreamRef: "abc", backend: "cuda", sha256: "def",
      installedAt: new Date().toISOString(), llamaCppVersion: "b1234",
    });
    const builds = await listBuilds(join(tmpDir, "store"));
    expect(builds).toHaveLength(1);
    expect(builds[0].id).toBe("upstream-cuda-b1234");
  });

  it("writeMeta and readMeta round-trip", async () => {
    const buildDir = join(tmpDir, "store", "test-build");
    await mkdir(buildDir, { recursive: true });
    const meta = {
      id: "test-build", target: "test", buildNum: 1,
      upstreamRef: "abc", backend: "cpu", sha256: "def",
      installedAt: "2026-08-02T00:00:00Z", llamaCppVersion: "b1",
    };
    await writeMeta(buildDir, meta);
    const read = await readMeta(buildDir);
    expect(read).toEqual(meta);
  });

  it("getActiveBuild returns null when no symlink", async () => {
    const active = await getActiveBuild(join(tmpDir, "store"), join(tmpDir, "bin"));
    expect(active).toBeNull();
  });
});
