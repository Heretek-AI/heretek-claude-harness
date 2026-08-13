import { readFile, writeFile, mkdir } from "fs/promises";
import { join } from "path";

export interface HeretekConfig {
  defaultQuant: string;
  safetyMarginPct: number;
  flashAttn: boolean;
  cacheDtype: string;
  preferredBackend?: string;
  autoUpdate: boolean;
  defaultPort: number;
  host: string;
  storeDir: string;
  binDir: string;
  lemonade?: { configPath: string; autoSync: boolean };
}

export const DEFAULT_CONFIG: HeretekConfig = {
  defaultQuant: "Q4_K_M",
  safetyMarginPct: 5.0,
  flashAttn: true,
  cacheDtype: "f16",
  autoUpdate: true,
  defaultPort: 8080,
  host: "localhost",
  storeDir: "~/.heretek/store",
  binDir: "~/.heretek/bin",
};

export async function loadConfig(baseDir: string): Promise<HeretekConfig> {
  const configPath = join(baseDir, "config.json");
  try {
    const raw = await readFile(configPath, "utf-8");
    return { ...DEFAULT_CONFIG, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

export async function saveConfig(baseDir: string, config: HeretekConfig): Promise<void> {
  await mkdir(baseDir, { recursive: true });
  const configPath = join(baseDir, "config.json");
  await writeFile(configPath, JSON.stringify(config, null, 2));
}
