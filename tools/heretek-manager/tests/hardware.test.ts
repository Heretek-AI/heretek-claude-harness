// tests/hardware.test.ts
import { describe, it, expect } from "vitest";
import { parseNvidiaSmi, parseLspci, type GpuInfo } from "../src/core/hardware.js";

describe("hardware detection", () => {
  const nvidiaSmiOutput = `name, driver_version, memory.total, compute_cap
NVIDIA GeForce RTX 4090, 535.129.03, 24564 MiB, 8.9`;

  it("parseNvidiaSmi extracts GPU info", () => {
    const gpus = parseNvidiaSmi(nvidiaSmiOutput);
    expect(gpus).toHaveLength(1);
    expect(gpus[0].name).toContain("RTX 4090");
    expect(gpus[0].vramMb).toBe(24564);
    expect(gpus[0].vendor).toBe("nvidia");
    expect(gpus[0].computeCapability).toBe("8.9");
  });

  it("parseNvidiaSmi handles empty output", () => {
    const gpus = parseNvidiaSmi("");
    expect(gpus).toHaveLength(0);
  });

  it("parseLspci detects NVIDIA vendor", () => {
    const lspci = `01:00.0 VGA compatible controller: NVIDIA Corporation Device 2684 (rev a1)`;
    const devices = parseLspci(lspci);
    expect(devices.length).toBeGreaterThanOrEqual(1);
  });

  it("parseLspci handles empty output", () => {
    const devices = parseLspci("");
    expect(devices).toHaveLength(0);
  });
});
