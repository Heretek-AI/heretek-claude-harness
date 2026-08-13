import { readFile, writeFile, mkdir } from "fs/promises";
import { join } from "path";

export interface ManifestEntry {
  target: string;
  buildNum: number;
  backend: string;
  downloadUrl: string;
  sha256: string;
  upstreamRef: string;
}

export interface Manifest {
  version: number;
  builds: ManifestEntry[];
}

const DEFAULT_MANIFEST_URL = "https://raw.githubusercontent.com/Heretek-AI/llama-builds/main/manifest.json";

export async function fetchManifest(cacheDir: string, manifestUrl?: string): Promise<Manifest> {
  const url = manifestUrl || DEFAULT_MANIFEST_URL;
  const cachePath = join(cacheDir, "manifest.json");
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const manifest = await res.json() as Manifest;
    await mkdir(cacheDir, { recursive: true });
    await writeFile(cachePath, JSON.stringify(manifest, null, 2));
    return manifest;
  } catch {
    try {
      const raw = await readFile(cachePath, "utf-8");
      return JSON.parse(raw);
    } catch {
      throw new Error("No manifest available (network failed, no cache)");
    }
  }
}

export function resolveBuild(manifest: Manifest, target: string, buildNum?: number): ManifestEntry | undefined {
  const candidates = manifest.builds.filter(b => b.target === target);
  if (candidates.length === 0) return undefined;
  if (buildNum) return candidates.find(b => b.buildNum === buildNum);
  return candidates.sort((a, b) => b.buildNum - a.buildNum)[0];
}
