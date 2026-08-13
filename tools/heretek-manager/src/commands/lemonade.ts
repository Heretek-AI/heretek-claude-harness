import { Command } from "commander";
import { detectLemonade, setupLemonade } from "../core/lemonade.js";
import { listBuilds } from "../core/store.js";
import { homedir } from "os";
import { join } from "path";

const setupCommand = new Command("setup")
  .description("Detect lemonade and configure custom backends")
  .action(async () => {
    const baseDir = join(homedir(), ".heretek");
    const configPath = join(homedir(), ".cache/lemonade/config.json");
    const lemonade = await detectLemonade(configPath);
    if (!lemonade) {
      console.log("❌ Lemonade not detected. Install lemonade first: https://lemonade-server.ai");
      return;
    }
    console.log("✅ Lemonade detected");
    const builds = await listBuilds(join(baseDir, "store"));
    if (builds.length === 0) {
      console.log("⚠️  No builds installed. Run `heretek-manager install` first.");
      return;
    }
    await setupLemonade(configPath, builds.map(b => ({
      id: b.id, backend: b.backend,
      binPath: join(baseDir, "store", b.id, "bin"),
    })));
    console.log(`🔗 Configured ${builds.length} build(s) in lemonade`);
  });

const lemonadeStatusCommand = new Command("status")
  .description("Show lemonade configuration status")
  .action(async () => {
    const configPath = join(homedir(), ".cache/lemonade/config.json");
    const lemonade = await detectLemonade(configPath);
    if (!lemonade) { console.log("❌ Lemonade not detected"); return; }
    console.log(`✅ Lemonade config: ${configPath}`);
  });

export const lemonadeCommand = new Command("lemonade")
  .description("Configure lemonade server backends")
  .addCommand(setupCommand)
  .addCommand(lemonadeStatusCommand);
