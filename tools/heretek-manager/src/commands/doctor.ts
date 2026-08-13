import { Command } from "commander";
import { detectHardware } from "../core/hardware.js";
import { listBuilds } from "../core/store.js";
import { getActiveSymlink } from "../core/symlinks.js";
import { loadConfig } from "../core/config.js";
import { homedir } from "os";
import { join } from "path";

export const doctorCommand = new Command("doctor")
  .description("Run diagnostics")
  .action(async () => {
    const baseDir = join(homedir(), ".heretek");
    console.log("🔍 heretek-manager diagnostics\n");

    console.log("Hardware:");
    try {
      const hw = await detectHardware();
      console.log(`  GPUs: ${hw.gpus.length}`);
      for (const g of hw.gpus) console.log(`    ${g.name} (${g.vramMb} MiB, ${g.vendor})`);
      console.log(`  CPU: ${hw.cpu.model} (${hw.cpu.cores} cores)`);
      console.log(`  RAM: ${hw.cpu.ramMb} MiB`);
    } catch (err) {
      console.log(`  ❌ Hardware detection failed: ${(err as Error).message}`);
    }

    console.log("\nBuilds:");
    const builds = await listBuilds(join(baseDir, "store"));
    console.log(`  Installed: ${builds.length}`);
    const active = await getActiveSymlink(join(baseDir, "bin"));
    console.log(`  Active: ${active || "none"}`);

    console.log("\nConfig:");
    const config = await loadConfig(baseDir);
    console.log(`  Default quant: ${config.defaultQuant}`);
    console.log(`  Flash attention: ${config.flashAttn}`);
    console.log(`  Safety margin: ${config.safetyMarginPct}%`);
  });
