import { describe, it, expect } from "vitest";
import { resolveBuild, type Manifest } from "../src/core/registry.js";

describe("registry", () => {
  const manifest: Manifest = {
    version: 1,
    builds: [
      { target: "upstream-cuda", buildNum: 1234, backend: "cuda", downloadUrl: "https://example.com/a.tar.gz", sha256: "aaa", upstreamRef: "abc" },
      { target: "upstream-cuda", buildNum: 5678, backend: "cuda", downloadUrl: "https://example.com/b.tar.gz", sha256: "bbb", upstreamRef: "def" },
      { target: "upstream-rocm", buildNum: 9012, backend: "rocm", downloadUrl: "https://example.com/c.tar.gz", sha256: "ccc", upstreamRef: "ghi" },
    ],
  };

  it("resolveBuild finds latest build for target", () => {
    const result = resolveBuild(manifest, "upstream-cuda");
    expect(result?.buildNum).toBe(5678);
  });

  it("resolveBuild finds specific build number", () => {
    const result = resolveBuild(manifest, "upstream-cuda", 1234);
    expect(result?.buildNum).toBe(1234);
  });

  it("resolveBuild returns undefined for unknown target", () => {
    const result = resolveBuild(manifest, "nonexistent");
    expect(result).toBeUndefined();
  });

  it("resolveBuild returns undefined for non-existent build number", () => {
    const result = resolveBuild(manifest, "upstream-cuda", 9999);
    expect(result).toBeUndefined();
  });
});
