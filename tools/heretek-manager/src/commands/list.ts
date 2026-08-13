// src/commands/list.ts
import { Command } from "commander";
import { listBuilds, getActiveBuild } from "../core/store.js";
import { homedir } from "os";
import { join } from "path";

export const listCommand = new Command("list")
  .description("List installed builds")
  .action(async () => {
    const baseDir = join(homedir(), ".heretek");
    const builds = await listBuilds(join(baseDir, "store"));
    const active = await getActiveBuild(join(baseDir, "store"), join(baseDir, "bin"));
    if (builds.length === 0) {
      console.log("No builds installed. Run `heretek-manager install <target>` to get started.");
      return;
    }
    console.log("Installed builds:\n");
    for (const build of builds) {
      const marker = active?.id === build.id ? " ← active" : "";
      console.log(`  ${build.id} (${build.backend})${marker}`);
      console.log(`    Build: ${build.buildNum}, Upstream: ${build.upstreamRef}`);
      console.log(`    Installed: ${build.installedAt}\n`);
    }
  });
