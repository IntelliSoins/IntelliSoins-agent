// Parameterized OpenProse PostgreSQL state operations for prose-pg CLI batching.
import type { Sql } from "postgres";

export type BindingKind = "input" | "output" | "let" | "const";

export type ExecutionStatus = "pending" | "executing" | "completed" | "failed" | "skipped";

export type BindingUpsertInput = {
  op: "binding-upsert";
  runId: string;
  name: string;
  kind: BindingKind;
  value: string;
  sourceStatement?: string;
  executionId?: number | null;
  attachmentPath?: string | null;
};

export type BindingGetInput = {
  op: "binding-get";
  runId: string;
  name: string;
  executionId?: number | null;
};

export type ExecutionUpsertInput = {
  op: "execution-upsert";
  runId: string;
  statementIndex: number;
  statementText?: string;
  status: ExecutionStatus;
  parentId?: number | null;
  errorMessage?: string | null;
  metadata?: Record<string, unknown>;
};

export type RunRegisterInput = {
  op: "run-register";
  runId: string;
  programPath?: string | null;
  programSource?: string | null;
  status?: "running" | "completed" | "failed" | "interrupted";
};

export type ProsePgBatchOp =
  | BindingUpsertInput
  | BindingGetInput
  | ExecutionUpsertInput
  | RunRegisterInput;

export type ProsePgBatchFile = {
  ops: ProsePgBatchOp[];
};

export type ProsePgOpResult =
  | { op: "binding-upsert"; ok: true }
  | { op: "binding-get"; value: string | null }
  | { op: "execution-upsert"; id: number }
  | { op: "run-register"; ok: true };

export type ProsePgSqlClient = Sql;

export async function checkConnection(sql: ProsePgSqlClient): Promise<void> {
  await sql`SELECT 1`;
}

export async function initSchema(sql: ProsePgSqlClient, schemaSql: string): Promise<void> {
  await sql.unsafe(schemaSql);
}

export async function upsertBinding(
  sql: ProsePgSqlClient,
  input: Omit<BindingUpsertInput, "op">,
): Promise<void> {
  const executionId = input.executionId ?? null;
  await sql`
    INSERT INTO openprose.bindings (
      name,
      run_id,
      execution_id,
      kind,
      value,
      source_statement,
      attachment_path,
      updated_at
    )
    VALUES (
      ${input.name},
      ${input.runId},
      ${executionId},
      ${input.kind},
      ${input.value},
      ${input.sourceStatement ?? null},
      ${input.attachmentPath ?? null},
      NOW()
    )
    ON CONFLICT (name, run_id, COALESCE(execution_id, -1))
    DO UPDATE SET
      kind = EXCLUDED.kind,
      value = EXCLUDED.value,
      source_statement = EXCLUDED.source_statement,
      attachment_path = EXCLUDED.attachment_path,
      updated_at = NOW()
  `;
}

export async function getBinding(
  sql: ProsePgSqlClient,
  input: Omit<BindingGetInput, "op">,
): Promise<string | null> {
  const executionId = input.executionId ?? null;
  const rows = await sql<{ value: string | null }[]>`
    SELECT value
    FROM openprose.bindings
    WHERE name = ${input.name}
      AND run_id = ${input.runId}
      AND (
        (${executionId}::integer IS NULL AND execution_id IS NULL)
        OR execution_id = ${executionId}
      )
    LIMIT 1
  `;
  return rows[0]?.value ?? null;
}

export async function upsertExecution(
  sql: ProsePgSqlClient,
  input: Omit<ExecutionUpsertInput, "op">,
): Promise<number> {
  const metadata = input.metadata ?? {};
  const rows = await sql<{ id: number }[]>`
    INSERT INTO openprose.execution (
      run_id,
      statement_index,
      statement_text,
      status,
      started_at,
      parent_id,
      error_message,
      metadata
    )
    VALUES (
      ${input.runId},
      ${input.statementIndex},
      ${input.statementText ?? null},
      ${input.status},
      CASE WHEN ${input.status} = 'executing' THEN NOW() ELSE NULL END,
      ${input.parentId ?? null},
      ${input.errorMessage ?? null},
      ${sql.json(metadata)}
    )
    RETURNING id
  `;
  const id = rows[0]?.id;
  if (typeof id !== "number") {
    throw new Error("Failed to insert execution row.");
  }
  return id;
}

export async function registerRun(
  sql: ProsePgSqlClient,
  input: Omit<RunRegisterInput, "op">,
): Promise<void> {
  const status = input.status ?? "running";
  await sql`
    INSERT INTO openprose.run (
      id,
      program_path,
      program_source,
      status,
      state_mode,
      updated_at
    )
    VALUES (
      ${input.runId},
      ${input.programPath ?? null},
      ${input.programSource ?? null},
      ${status},
      'postgres',
      NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
      program_path = COALESCE(EXCLUDED.program_path, openprose.run.program_path),
      program_source = COALESCE(EXCLUDED.program_source, openprose.run.program_source),
      status = EXCLUDED.status,
      updated_at = NOW()
  `;
}

export async function runBatchOp(
  sql: ProsePgSqlClient,
  op: ProsePgBatchOp,
): Promise<ProsePgOpResult> {
  switch (op.op) {
    case "binding-upsert":
      await upsertBinding(sql, op);
      return { op: "binding-upsert", ok: true };
    case "binding-get":
      return { op: "binding-get", value: await getBinding(sql, op) };
    case "execution-upsert":
      return { op: "execution-upsert", id: await upsertExecution(sql, op) };
    case "run-register":
      await registerRun(sql, op);
      return { op: "run-register", ok: true };
    default: {
      const unknownOp = (op as { op?: string }).op ?? "unknown";
      throw new Error(`Unsupported batch op: ${unknownOp}`);
    }
  }
}

export async function runBatch(
  sql: ProsePgSqlClient,
  ops: ProsePgBatchOp[],
): Promise<ProsePgOpResult[]> {
  if (ops.length === 0) {
    return [];
  }
  const results: ProsePgOpResult[] = [];
  await sql.begin(async (tx) => {
    for (const op of ops) {
      results.push(await runBatchOp(tx, op));
    }
  });
  return results;
}

export function parseBatchFile(payload: unknown): ProsePgBatchFile {
  if (!payload || typeof payload !== "object" || !("ops" in payload)) {
    throw new Error("Batch file must be a JSON object with an ops array.");
  }
  const ops = (payload as { ops: unknown }).ops;
  if (!Array.isArray(ops)) {
    throw new Error("Batch file ops must be an array.");
  }
  return { ops: ops as ProsePgBatchOp[] };
}
