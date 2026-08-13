import { readFile, writeFile, mkdir } from "fs/promises";

export interface LemonadeConfig {
  configPath: string;
  detected: boolean;
}

export async function detectLemonade(configPath: string): Promise<LemonadeConfig | null> {
  try {
    await readFile(configPath, "utf-8");
    return { configPath, detected: true };
  } catch {
    return null;
  }
}

interface BackendPath {
  id: string;
  backend: string;
  binPath: string;
}

export async function setupLemonade(configPath: string, backends: BackendPath[]): Promise<void> {
  let config: Record<string, unknown> = {};
  try { config = JSON.parse(await readFile(configPath, "utf-8")); } catch { /* start fresh */ }
  if (!config.llamacpp) config.llamacpp = {};
  const llamacpp = config.llamacpp as Record<string, string>;
  const BACKEND_MAP: Record<string, string> = {
    cuda: "cuda_bin", rocm: "rocm_bin", vulkan: "vulkan_bin", cpu: "cpu_bin",
  };
  for (const backend of backends) {
    const key = BACKEND_MAP[backend.backend];
    if (key) llamacpp[key] = backend.binPath;
  }
  const dir = configPath.substring(0, configPath.lastIndexOf("/"));
  await mkdir(dir, { recursive: true });
  await writeFile(configPath, JSON.stringify(config, null, 2));
}
