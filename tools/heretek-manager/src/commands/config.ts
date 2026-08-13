import { Command } from "commander";
import { loadConfig, saveConfig, DEFAULT_CONFIG } from "../core/config.js";
import { homedir } from "os";
import { join } from "path";

const showCommand = new Command("show")
  .description("Show current configuration")
  .action(async () => {
    const baseDir = join(homedir(), ".heretek");
    const config = await loadConfig(baseDir);
    console.log(JSON.stringify(config, null, 2));
  });

const setCommand = new Command("set")
  .description("Set a configuration value")
  .argument("<key>", "Configuration key (e.g., default-quant)")
  .argument("<value>", "Value to set")
  .action(async (key, value) => {
    const baseDir = join(homedir(), ".heretek");
    const config = await loadConfig(baseDir);
    const configKey = key.replace(/-([a-z])/g, (_: string, c: string) => c.toUpperCase());
    (config as unknown as Record<string, unknown>)[configKey] = value;
    await saveConfig(baseDir, config);
    console.log(`✅ Set ${key} = ${value}`);
  });

export const configCommand = new Command("config")
  .description("View or update configuration")
  .addCommand(showCommand)
  .addCommand(setCommand);
