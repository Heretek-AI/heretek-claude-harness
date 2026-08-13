import { describe, it, expect } from "vitest";

describe("installer", () => {
  it("InstallResult has required fields", () => {
    type TestResult = {
      id: string; path: string; binary: string; verified: boolean;
    };
    const result: TestResult = {
      id: "upstream-cuda-b1234",
      path: "/home/user/.heretek/store/upstream-cuda-b1234",
      binary: "/home/user/.heretek/store/upstream-cuda-b1234/bin/llama-server",
      verified: true,
    };
    expect(result.verified).toBe(true);
  });
});
