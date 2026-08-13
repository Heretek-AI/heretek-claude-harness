import { readFile, writeFile, readdir, mkdir, readlink } from "fs/promises";
import { join } from "path";

export interface InstalledBuild {
  id: string;
  target: string;
  buildNum: number;
  upstreamRef: string;
  backend: string;
  sha256: string;
  installedAt: string;
  llamaCppVersion: string;
}

export async function listBuilds(storeDir: string): Promise<InstalledBuild[]> {
  await mkdir(storeDir, { recursive: true });
  const entries = await readdir(storeDir, { withFileTypes: true });
  const builds: InstalledBuild[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    try {
      const meta = await readMeta(join(storeDir, entry.name));
      builds.push(meta);
    } catch { /* skip dirs without META.json */ }
  }
  return builds;
}

export async function readMeta(buildDir: string): Promise<InstalledBuild> {
  const raw = await readFile(join(buildDir, "META.json"), "utf-8");
  return JSON.parse(raw);
}

export async function writeMeta(buildDir: string, meta: InstalledBuild): Promise<void> {
  await mkdir(buildDir, { recursive: true });
  await writeFile(join(buildDir, "META.json"), JSON.stringify(meta, null, 2));
}

export async function getActiveBuild(storeDir: string, binDir: string): Promise<InstalledBuild | null> {
  try {
    const target = await readlink(join(binDir, "llama-server"));
    const match = target.match(/store\/([^/]+)\//);
    if (!match) return null;
    return readMeta(join(storeDir, match[1]));
  } catch {
    return null;
  }
}
