import { mkdir, writeFile } from "fs/promises";
import { join } from "path";
import { execFile } from "child_process";
import { promisify } from "util";
import { createHash } from "crypto";
import type { ManifestEntry } from "./registry.js";
import type { InstalledBuild } from "./store.js";
import { writeMeta } from "./store.js";

const execFileAsync = promisify(execFile);

export interface InstallResult {
  id: string;
  path: string;
  binary: string;
  verified: boolean;
}

export async function installBuild(
  baseDir: string,
  entry: ManifestEntry,
  cacheDir: string,
): Promise<InstallResult> {
  const storeId = `${entry.target}-b${entry.buildNum}`;
  const storeDir = join(baseDir, "store", storeId);
  const downloadDir = join(cacheDir, "downloads");
  const tarPath = join(downloadDir, `${storeId}.tar.gz`);

  // 1. Download
  await mkdir(downloadDir, { recursive: true });
  const res = await fetch(entry.downloadUrl);
  if (!res.ok) throw new Error(`Download failed: HTTP ${res.status}`);
  const buffer = Buffer.from(await res.arrayBuffer());
  await writeFile(tarPath, buffer);

  // 2. SHA-256 verify
  const hash = createHash("sha256").update(buffer).digest("hex");
  const verified = hash === entry.sha256;
  if (!verified) throw new Error(`SHA-256 mismatch: expected ${entry.sha256}, got ${hash}`);

  // 3. Extract
  await mkdir(storeDir, { recursive: true });
  await execFileAsync("tar", ["xzf", tarPath, "-C", storeDir]);

  // 4. Write META.json
  const meta: InstalledBuild = {
    id: storeId, target: entry.target, buildNum: entry.buildNum,
    upstreamRef: entry.upstreamRef, backend: entry.backend,
    sha256: entry.sha256, installedAt: new Date().toISOString(),
    llamaCppVersion: `b${entry.buildNum}`,
  };
  await writeMeta(storeDir, meta);

  return {
    id: storeId, path: storeDir,
    binary: join(storeDir, "bin", "llama-server"),
    verified,
  };
}
