// src/commands/remove.ts
import { Command } from "commander";
import { rm } from "fs/promises";
import { homedir } from "os";
import { join } from "path";

export const removeCommand = new Command("remove")
  .description("Uninstall a build")
  .argument("<build-id>", "Build ID to remove")
  .action(async (buildId) => {
    const baseDir = join(homedir(), ".heretek");
    const storeDir = join(baseDir, "store", buildId);
    await rm(storeDir, { recursive: true, force: true });
    console.log(`🗑️  Removed: ${buildId}`);
  });
