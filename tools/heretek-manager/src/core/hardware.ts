// src/core/hardware.ts
import { execFile } from "child_process";
import { promisify } from "util";
import { readFile } from "fs/promises";
import { cpus } from "os";

const execFileAsync = promisify(execFile);

export interface GpuInfo {
  index: number;
  name: string;
  vramMb: number;
  driverVersion: string;
  computeCapability?: string;
  computeUnits?: number;
  memoryBandwidthGb?: number;
  isUnified: boolean;
  vendor: "nvidia" | "amd" | "intel" | "apple" | "unknown";
}

export interface CpuInfo {
  model: string;
  cores: number;
  ramMb: number;
}

export interface HardwareProfile {
  gpus: GpuInfo[];
  cpu: CpuInfo;
  detectedAt: string;
}

export function parseNvidiaSmi(output: string): GpuInfo[] {
  const lines = output.trim().split("\n").filter(l => l.trim());
  if (lines.length === 0) return [];
  // Skip header line if present
  const dataLines = lines[0].includes("name") ? lines.slice(1) : lines;
  return dataLines.map((line, i) => {
    const parts = line.split(",").map(s => s.trim());
    const name = parts[0] ?? "";
    const driver = parts[1] ?? "";
    const vramMatch = parts[2]?.match(/(\d+)\s*MiB/);
    const vramMb = vramMatch ? parseInt(vramMatch[1]) : 0;
    const cap = parts[3]?.trim();
    return {
      index: i, name, vramMb, driverVersion: driver,
      computeCapability: cap || undefined, vendor: "nvidia" as const,
      isUnified: false,
    };
  });
}

export function parseRocminfo(output: string): GpuInfo[] {
  const gpus: GpuInfo[] = [];
  const deviceBlocks = output.split("Device Type:").slice(1);
  deviceBlocks.forEach((block, i) => {
    if (!block.includes("GPU")) return;
    const nameMatch = block.match(/Marketing Name:\s*(.+)/);
    const vramMatch = block.match(/Memory.*?(\d+)\s*(MiB|GiB)/);
    const driverMatch = block.match(/Driver Version:\s*(.+)/);
    let vramMb = 0;
    if (vramMatch) {
      vramMb = parseInt(vramMatch[1]);
      if (vramMatch[2] === "GiB") vramMb *= 1024;
    }
    gpus.push({
      index: i, name: nameMatch?.[1]?.trim() ?? `AMD GPU ${i}`,
      vramMb, driverVersion: driverMatch?.[1]?.trim() ?? "",
      vendor: "amd", isUnified: false,
    });
  });
  return gpus;
}

export function parseLspci(output: string): { vendor: string; device: string }[] {
  const devices: { vendor: string; device: string }[] = [];
  for (const line of output.split("\n")) {
    const match = line.match(/VGA|3D|Display/);
    if (!match) continue;
    const vendorMatch = line.match(/(NVIDIA|AMD|Intel|ATI)/i);
    const deviceMatch = line.match(/:\s*(.+?)(?:\s*\(rev|$)/);
    devices.push({
      vendor: vendorMatch?.[1]?.toLowerCase() ?? "unknown",
      device: deviceMatch?.[1]?.trim() ?? "",
    });
  }
  return devices;
}

async function getTotalRamMb(): Promise<number> {
  try {
    const meminfo = await readFile("/proc/meminfo", "utf-8");
    const match = meminfo.match(/MemTotal:\s*(\d+)\s*kB/);
    return match ? Math.round(parseInt(match[1]) / 1024) : 0;
  } catch { return 0; }
}

export async function detectHardware(): Promise<HardwareProfile> {
  const gpus: GpuInfo[] = [];
  const cpuInfo = cpus()[0];
  const ramMb = await getTotalRamMb();

  // Try nvidia-smi
  try {
    const { stdout } = await execFileAsync("nvidia-smi", [
      "--query-gpu=name,driver_version,memory.total,compute_cap",
      "--format=csv,noheader",
    ]);
    gpus.push(...parseNvidiaSmi(stdout));
  } catch { /* not NVIDIA or nvidia-smi not available */ }

  // Try rocminfo if no NVIDIA GPUs found
  if (gpus.length === 0) {
    try {
      const { stdout } = await execFileAsync("rocminfo");
      gpus.push(...parseRocminfo(stdout));
    } catch { /* not AMD or rocminfo not available */ }
  }

  // Fallback to lspci
  if (gpus.length === 0) {
    try {
      const { stdout } = await execFileAsync("lspci", ["-v"]);
      const devices = parseLspci(stdout);
      devices.forEach((d, i) => {
        gpus.push({
          index: i, name: d.device, vramMb: 0, driverVersion: "",
          vendor: d.vendor as GpuInfo["vendor"], isUnified: false,
        });
      });
    } catch { /* lspci not available */ }
  }

  return {
    gpus,
    cpu: { model: `${cpuInfo?.model ?? "unknown"} @ ${(cpuInfo?.speed ?? 0)} MHz`, cores: cpus().length, ramMb },
    detectedAt: new Date().toISOString(),
  };
}
