#!/usr/bin/env node
// prose-pg CLI: pooled PostgreSQL access for OpenProse experimental postgres state.
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import postgres from "postgres";
import { requireOpenProsePostgresUrl } from "./connection.js";
import {
  checkConnection,
  getBinding,
  initSchema,
  parseBatchFile,
  registerRun,
  runBatch,
  upsertBinding,
  upsertExecution,
  type BindingKind,
  type ExecutionStatus,
} from "./ops.js";

const SCHEMA_PATH = path.join(path.dirname(fileURLToPath(import.meta.url)), "schema.sql");

function printJson(value: unknown): void {
  process.stdout.write(`${JSON.stringify(value)}\n`);
}

function usage(): void {
  process.stderr.write(`Usage:
  prose-pg check
  prose-pg init
  prose-pg binding-get --run-id <id> --name <name> [--execution-id <n>]
  prose-pg binding-upsert --run-id <id> --name <name> --kind <kind> --value <text> [--execution-id <n>] [--source-statement <text>]
  prose-pg execution-upsert --run-id <id> --statement-index <n> --status <status> [--statement-text <text>] [--parent-id <n>]
  prose-pg run-register --run-id <id> [--program-path <path>] [--program-source <text>] [--status <status>]
  prose-pg batch [--file <path>] [@ops.json]
`);
}

function readFlag(args: string[], flag: string): string | undefined {
  const index = args.indexOf(flag);
  if (index === -1) {
    return undefined;
  }
  return args[index + 1];
}

function readRequiredFlag(args: string[], flag: string): string {
  const value = readFlag(args, flag);
  if (!value) {
    throw new Error(`Missing required flag: ${flag}`);
  }
  return value;
}

function readOptionalIntFlag(args: string[], flag: string): number | null | undefined {
  const raw = readFlag(args, flag);
  if (raw == null) {
    return undefined;
  }
  if (raw === "null") {
    return null;
  }
  const parsed = Number(raw);
  if (!Number.isInteger(parsed)) {
    throw new Error(`Flag ${flag} must be an integer or null.`);
  }
  return parsed;
}

async function readBatchPayload(args: string[]): Promise<unknown> {
  const fileFlag = readFlag(args, "--file");
  const atArg = args.find((arg) => arg.startsWith("@"));
  const filePath = fileFlag ?? (atArg ? atArg.slice(1) : undefined);
  if (!filePath) {
    throw new Error("batch requires --file <path> or @ops.json");
  }
  const raw = await readFile(filePath, "utf8");
  return JSON.parse(raw) as unknown;
}

function createClient() {
  return postgres(requireOpenProsePostgresUrl(), {
    max: 1,
    idle_timeout: 20,
    connect_timeout: 10,
  });
}

async function runCommand(command: string, args: string[]): Promise<number> {
  if (command === "help" || command === "--help" || command === "-h") {
    usage();
    return 0;
  }

  const sql = createClient();
  try {
    switch (command) {
      case "check": {
        await checkConnection(sql);
        printJson({ ok: true });
        return 0;
      }
      case "init": {
        const schemaSql = await readFile(SCHEMA_PATH, "utf8");
        await initSchema(sql, schemaSql);
        printJson({ ok: true, schema: "openprose" });
        return 0;
      }
      case "binding-get": {
        const value = await getBinding(sql, {
          runId: readRequiredFlag(args, "--run-id"),
          name: readRequiredFlag(args, "--name"),
          executionId: readOptionalIntFlag(args, "--execution-id"),
        });
        printJson({ value });
        return 0;
      }
      case "binding-upsert": {
        await upsertBinding(sql, {
          runId: readRequiredFlag(args, "--run-id"),
          name: readRequiredFlag(args, "--name"),
          kind: readRequiredFlag(args, "--kind") as BindingKind,
          value: readRequiredFlag(args, "--value"),
          sourceStatement: readFlag(args, "--source-statement"),
          executionId: readOptionalIntFlag(args, "--execution-id"),
        });
        printJson({ ok: true });
        return 0;
      }
      case "execution-upsert": {
        const id = await upsertExecution(sql, {
          runId: readRequiredFlag(args, "--run-id"),
          statementIndex: Number(readRequiredFlag(args, "--statement-index")),
          status: readRequiredFlag(args, "--status") as ExecutionStatus,
          statementText: readFlag(args, "--statement-text"),
          parentId: readOptionalIntFlag(args, "--parent-id"),
          errorMessage: readFlag(args, "--error-message"),
        });
        printJson({ id });
        return 0;
      }
      case "run-register": {
        await registerRun(sql, {
          runId: readRequiredFlag(args, "--run-id"),
          programPath: readFlag(args, "--program-path"),
          programSource: readFlag(args, "--program-source"),
          status: readFlag(args, "--status") as
            | "running"
            | "completed"
            | "failed"
            | "interrupted"
            | undefined,
        });
        printJson({ ok: true });
        return 0;
      }
      case "batch": {
        const payload = await readBatchPayload(args);
        const batch = parseBatchFile(payload);
        const results = await runBatch(sql, batch.ops);
        printJson({ results });
        return 0;
      }
      default:
        usage();
        return 1;
    }
  } finally {
    await sql.end({ timeout: 5 });
  }
}

async function main(): Promise<void> {
  const [command, ...args] = process.argv.slice(2);
  if (!command) {
    usage();
    process.exit(1);
  }
  try {
    const code = await runCommand(command, args);
    process.exit(code);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`${message}\n`);
    process.exit(1);
  }
}

await main();
