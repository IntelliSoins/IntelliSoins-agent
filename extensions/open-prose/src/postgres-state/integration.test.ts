import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import postgres from "postgres";
import { describe, expect, it } from "vitest";
import { resolveOpenProsePostgresUrl } from "./connection.js";
import { checkConnection, initSchema, registerRun, runBatch } from "./ops.js";

const integrationUrl = resolveOpenProsePostgresUrl(process.env);
const describeIntegration = integrationUrl ? describe : describe.skip;

describeIntegration("openprose postgres integration", () => {
  it("initializes schema and runs a batch transaction", async () => {
    const sql = postgres(integrationUrl, { max: 1 });
    try {
      await checkConnection(sql);
      const schemaSql = await readFile(
        path.join(path.dirname(fileURLToPath(import.meta.url)), "schema.sql"),
        "utf8",
      );
      await initSchema(sql, schemaSql);

      const runId = `test-${Date.now()}`;
      const results = await runBatch(sql, [
        { op: "run-register", runId, programPath: "/tmp/test.prose" },
        {
          op: "binding-upsert",
          runId,
          name: "answer",
          kind: "let",
          value: "42",
        },
        { op: "binding-get", runId, name: "answer" },
      ]);

      expect(results[2]).toEqual({ op: "binding-get", value: "42" });
    } finally {
      await sql.end({ timeout: 5 });
    }
  });
});
