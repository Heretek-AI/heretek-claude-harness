// tests/symlinks.test.ts
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { setActiveBuild, getActiveSymlink } from "../src/core/symlinks.js";
import { mkdtemp, rm, mkdir, writeFile } from "fs/promises";
import { join } from "path";
import { tmpdir } from "os";

describe("symlinks", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await mkdtemp(join(tmpdir(), "heretek-symlink-"));
    await mkdir(join(tmpDir, "bin"), { recursive: true });
    await mkdir(join(tmpDir, "store/test-build/bin"), { recursive: true });
    await writeFile(join(tmpDir, "store/test-build/bin/llama-server"), "#!/bin/sh\necho test");
  });

  afterEach(async () => {
    await rm(tmpDir, { recursive: true, force: true });
  });

  it("setActiveBuild creates symlink", async () => {
    await setActiveBuild(tmpDir, "test-build");
    const target = await getActiveSymlink(join(tmpDir, "bin"));
    expect(target).toContain("test-build");
  });

  it("setActiveBuild atomically replaces existing symlink", async () => {
    await setActiveBuild(tmpDir, "test-build");
    await mkdir(join(tmpDir, "store/test-build2/bin"), { recursive: true });
    await writeFile(join(tmpDir, "store/test-build2/bin/llama-server"), "#!/bin/sh\necho test2");
    await setActiveBuild(tmpDir, "test-build2");
    const target = await getActiveSymlink(join(tmpDir, "bin"));
    expect(target).toContain("test-build2");
  });

  it("getActiveSymlink returns null when no symlink", async () => {
    const target = await getActiveSymlink(join(tmpDir, "bin"));
    expect(target).toBeNull();
  });
});
