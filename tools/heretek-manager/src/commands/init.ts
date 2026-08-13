// src/commands/init.ts
import { Command } from "commander";
import { detectHardware } from "../core/hardware.js";
import { fetchManifest } from "../core/registry.js";
import { homedir } from "os";
import { join } from "path";

export const initCommand = new Command("init")
  .description("Initialize: detect hardware and recommend builds")
  .option("--no-update", "Skip checking for new builds")
  .action(async (opts) => {
    const baseDir = join(homedir(), ".heretek");
    const cacheDir = join(baseDir, "cache");

    console.log("🔍 Detecting hardware...");
    const hw = await detectHardware();
    console.log(`   Found ${hw.gpus.length} GPU(s), ${hw.cpu.cores} CPU cores`);

    if (hw.gpus.length === 0) {
      console.log("   ⚠️  No GPUs detected. CPU-only mode.");
    } else {
      for (const gpu of hw.gpus) {
        console.log(`   GPU ${gpu.index}: ${gpu.name} (${gpu.vramMb} MiB, ${gpu.vendor})`);
      }
    }

    if (opts.update) {
      console.log("\n📦 Fetching build manifest...");
      try {
        const manifest = await fetchManifest(cacheDir);
        console.log(`   Found ${manifest.builds.length} available builds`);
        const vendor = hw.gpus[0]?.vendor ?? "unknown";
        const backendMap: Record<string, string> = { nvidia: "cuda", amd: "rocm", intel: "vulkan" };
        const targetBackend = backendMap[vendor] ?? "cpu";
        const matched = manifest.builds.filter(b => b.backend === targetBackend);
        if (matched.length > 0) {
          console.log(`\n✅ Recommended builds for ${vendor} (${targetBackend}):`);
          for (const build of matched.slice(0, 3)) {
            console.log(`   - ${build.target} (build ${build.buildNum})`);
          }
        } else {
          console.log(`\n   No builds found for backend: ${targetBackend}`);
        }
      } catch (err) {
        console.log(`   ⚠️  Failed to fetch manifest: ${(err as Error).message}`);
      }
    }

    console.log("\n✨ Run `heretek-manager install <target>` to install a build.");
  });
