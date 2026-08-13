import { Command } from "commander";
import { initCommand } from "./commands/init.js";
import { installCommand } from "./commands/install.js";
import { listCommand } from "./commands/list.js";
import { useCommand } from "./commands/use.js";
import { removeCommand } from "./commands/remove.js";
import { runCommand } from "./commands/run.js";
import { configCommand } from "./commands/config.js";
import { doctorCommand } from "./commands/doctor.js";
import { lemonadeCommand } from "./commands/lemonade.js";

const program = new Command();
program
  .name("heretek-manager")
  .description("Local AI management platform for llama.cpp")
  .version("0.1.0");

program.addCommand(initCommand);
program.addCommand(installCommand);
program.addCommand(listCommand);
program.addCommand(useCommand);
program.addCommand(removeCommand);
program.addCommand(runCommand);
program.addCommand(configCommand);
program.addCommand(doctorCommand);
program.addCommand(lemonadeCommand);

program.parse();
