// src/commands/use.ts
import { Command } from "commander";
import { setActiveBuild } from "../core/symlinks.js";
import { homedir } from "os";
import { join } from "path";

export const useCommand = new Command("use")
  .description("Switch the active build")
  .argument("<build-id>", "Build ID (e.g., upstream-cuda-b1234)")
  .action(async (buildId) => {
    const baseDir = join(homedir(), ".heretek");
    await setActiveBuild(baseDir, buildId);
    console.log(`🔗 Active build: ${buildId}`);
  });
