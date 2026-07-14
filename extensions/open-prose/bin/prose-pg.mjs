#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const cliPath = path.join(here, "../src/postgres-state/cli.ts");
const require = createRequire(import.meta.url);
const tsxCli = require.resolve("tsx/cli");

const result = spawnSync(process.execPath, [tsxCli, cliPath, ...process.argv.slice(2)], {
  stdio: "inherit",
  env: process.env,
});
process.exit(result.status ?? 1);
