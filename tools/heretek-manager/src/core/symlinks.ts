// src/core/symlinks.ts
import { symlink, readlink, rename, unlink } from "fs/promises";
import { join } from "path";

export async function setActiveBuild(baseDir: string, storeId: string): Promise<void> {
  const binDir = join(baseDir, "bin");
  const storePath = join(baseDir, "store", storeId, "bin", "llama-server");
  const linkPath = join(binDir, "llama-server");
  const tmpPath = join(binDir, "llama-server.tmp");

  let previousTarget: string | null = null;
  try { previousTarget = await readlink(linkPath); } catch { /* no existing link */ }

  try {
    await symlink(storePath, tmpPath);
    await rename(tmpPath, linkPath);
  } catch (err) {
    try { await unlink(tmpPath); } catch { /* ignore */ }
    if (previousTarget) {
      try { await symlink(previousTarget, linkPath); } catch { /* ignore */ }
    }
    throw err;
  }
}

export async function getActiveSymlink(binDir: string): Promise<string | null> {
  try { return await readlink(join(binDir, "llama-server")); }
  catch { return null; }
}
