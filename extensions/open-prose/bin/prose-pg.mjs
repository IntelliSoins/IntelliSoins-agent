#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cliPath = path.join(path.dirname(fileURLToPath(import.meta.url)), "../src/postgres-state/cli.ts");
const result = spawnSync(
  process.execPath,
  ["--experimental-strip-types", cliPath, ...process.argv.slice(2)],
  { stdio: "inherit", env: process.env },
);
process.exit(result.status ?? 1);
