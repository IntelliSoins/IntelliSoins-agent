import { describe, expect, it } from "vitest";
import {
  getBinding,
  parseBatchFile,
  registerRun,
  runBatch,
  runBatchOp,
  upsertBinding,
  type ProsePgSqlClient,
} from "./ops.js";

type SqlCall = {
  strings: TemplateStringsArray;
  values: unknown[];
};

function createMockSql(calls: SqlCall[]): ProsePgSqlClient {
  const sql = (async (strings: TemplateStringsArray, ...values: unknown[]) => {
    calls.push({ strings, values });
    if (strings.join("").includes("SELECT value")) {
      return [{ value: "mock-value" }];
    }
    if (strings.join("").includes("RETURNING id")) {
      return [{ id: 42 }];
    }
    return [];
  }) as ProsePgSqlClient;
  sql.unsafe = async () => undefined;
  sql.json = (value: unknown) => value;
  sql.begin = async (fn) => fn(sql);
  return sql;
}

describe("parseBatchFile", () => {
  it("parses a valid batch payload", () => {
    expect(
      parseBatchFile({
        ops: [{ op: "binding-get", runId: "run-1", name: "research" }],
      }),
    ).toEqual({
      ops: [{ op: "binding-get", runId: "run-1", name: "research" }],
    });
  });

  it("rejects invalid payloads", () => {
    expect(() => parseBatchFile(null)).toThrow(/ops array/i);
    expect(() => parseBatchFile({ ops: "nope" })).toThrow(/ops must be an array/i);
  });
});

describe("postgres state ops", () => {
  it("upsertBinding issues parameterized insert SQL", async () => {
    const calls: SqlCall[] = [];
    const sql = createMockSql(calls);
    await upsertBinding(sql, {
      runId: "run-1",
      name: "research",
      kind: "let",
      value: "findings",
      sourceStatement: "let research = session: researcher",
      executionId: null,
    });
    expect(calls).toHaveLength(1);
    expect(calls[0]?.values).toContain("run-1");
    expect(calls[0]?.values).toContain("research");
  });

  it("getBinding returns the first value", async () => {
    const calls: SqlCall[] = [];
    const sql = createMockSql(calls);
    await expect(
      getBinding(sql, { runId: "run-1", name: "research", executionId: 43 }),
    ).resolves.toBe("mock-value");
  });

  it("registerRun writes run metadata", async () => {
    const calls: SqlCall[] = [];
    const sql = createMockSql(calls);
    await registerRun(sql, {
      runId: "run-1",
      programPath: "/tmp/program.prose",
      programSource: 'session "hello"',
    });
    expect(calls[0]?.values).toContain("run-1");
    expect(calls[0]?.values).toContain("/tmp/program.prose");
  });

  it("runBatch executes ops in a transaction", async () => {
    const calls: SqlCall[] = [];
    const sql = createMockSql(calls);
    const results = await runBatch(sql, [
      { op: "run-register", runId: "run-1" },
      { op: "binding-upsert", runId: "run-1", name: "a", kind: "let", value: "1" },
      { op: "binding-get", runId: "run-1", name: "a" },
    ]);
    expect(results).toEqual([
      { op: "run-register", ok: true },
      { op: "binding-upsert", ok: true },
      { op: "binding-get", value: "mock-value" },
    ]);
    expect(calls.length).toBeGreaterThanOrEqual(3);
  });

  it("runBatchOp rejects unknown ops", async () => {
    const sql = createMockSql([]);
    await expect(runBatchOp(sql, { op: "unknown" } as never)).rejects.toThrow(
      /unsupported batch op/i,
    );
  });
});
