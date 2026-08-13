#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const cliScript = path.resolve(__dirname, "..", "scripts", "heretek_cli.py");
const pythonExec =
	process.env.PYTHON || (process.platform === "win32" ? "python" : "python3");

const result = spawnSync(pythonExec, [cliScript, ...process.argv.slice(2)], {
	stdio: "inherit",
	env: process.env,
});

if (result.error) {
	console.error(
		`heretek error: Failed to execute Python (${pythonExec}): ${result.error.message}`,
	);
	process.exit(1);
}

process.exit(result.status !== null ? result.status : 0);
