// src/commands/install.ts
import { Command } from "commander";
import { installBuild } from "../core/installer.js";
import { fetchManifest, resolveBuild } from "../core/registry.js";
import { setActiveBuild } from "../core/symlinks.js";
import { homedir } from "os";
import { join } from "path";

export const installCommand = new Command("install")
  .description("Install a build from the llama-builds registry")
  .argument("<target>", "Build target (e.g., upstream-cuda)")
  .option("--build <num>", "Pin to specific build number")
  .option("--active", "Set as active build after install")
  .action(async (target, opts) => {
    const baseDir = join(homedir(), ".heretek");
    const cacheDir = join(baseDir, "cache");
    console.log("📦 Fetching manifest...");
    const manifest = await fetchManifest(cacheDir);
    const buildNum = opts.build ? parseInt(opts.build) : undefined;
    const entry = resolveBuild(manifest, target, buildNum);
    if (!entry) {
      console.error(`❌ Build not found: ${target}${buildNum ? `@b${buildNum}` : ""}`);
      process.exit(1);
    }
    console.log(`📥 Installing ${entry.target} build ${entry.buildNum}...`);
    const result = await installBuild(baseDir, entry, cacheDir);
    console.log(`✅ Installed: ${result.id}`);
    if (opts.active) {
      await setActiveBuild(baseDir, result.id);
      console.log(`🔗 Set as active build`);
    }
  });
