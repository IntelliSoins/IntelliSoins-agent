// Local RAG pipeline methods (Intellisoins fork, 100% local — Loi 25): ingest documents
// through the openclaw_rag_ingest.py pipeline and search the pgvector sidecar (:8100).
import { execFile, spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import {
  ErrorCodes,
  errorShape,
  formatValidationErrors,
  validateRagIngestParams,
  validateRagJobsParams,
  validateRagSearchParams,
  validateRagSourcesParams,
} from "../../../packages/gateway-protocol/src/index.js";
import type { ErrorShape, RagJob } from "../../../packages/gateway-protocol/src/index.js";
import { resolveStateDir } from "../../config/paths.js";
import { formatErrorMessage } from "../../infra/errors.js";
import { FsSafeError, readSecureFile } from "../../infra/fs-safe.js";
import type { GatewayRequestHandlers } from "./types.js";

const SIDECAR_URL = "http://127.0.0.1:8100";
const VECTOR_STORE_ID = "41e70e3d-cbbe-45a2-b185-9e8df3f8d7b5"; // openclaw-docs (DB openclaw_pgvector)
const INGEST_SCRIPT = path.join(homedir(), "ai-servers", "scripts", "openclaw_rag_ingest.py");
const INBOX_DIR = path.join(homedir(), "openclaw", "rag-documents");
const SIDECAR_TIMEOUT_MS = 30_000;
const MAX_TRACKED_JOBS = 50;
const MAX_CAPTURED_OUTPUT = 64_000;
// Mirror of SUPPORTED in openclaw_rag_ingest.py — reject unsupported uploads before spawning.
const SUPPORTED_EXTENSIONS = new Set([
  ".pdf",
  ".docx",
  ".pptx",
  ".xlsx",
  ".md",
  ".html",
  ".htm",
  ".txt",
  ".png",
  ".jpg",
  ".jpeg",
  ".tiff",
  ".webp",
  ".csv",
  ".adoc",
]);

const ragJobs = new Map<string, RagJob>();

const SIDECAR_KEY_ENV = "LITELLM_PGVECTOR_API_KEY";
const SIDECAR_KEY_NAME = "litellm-pgvector-api-key";

// Read the sidecar key once and cache it for the process lifetime; never log it or put it in
// error messages. Sources, in order: env var (portable/testable), the canonical credentials
// file, then the macOS keychain (darwin only) so existing macOS setups keep working.
let sidecarApiKeyPromise: Promise<string> | null = null;

function getSidecarApiKey(): Promise<string> {
  return (sidecarApiKeyPromise ??= readSidecarApiKey().catch((err: unknown) => {
    // Allow a retry on the next request instead of caching the failure forever.
    sidecarApiKeyPromise = null;
    throw err;
  }));
}

async function readSidecarApiKey(): Promise<string> {
  const fromEnv = process.env[SIDECAR_KEY_ENV]?.trim();
  if (fromEnv) {
    return fromEnv;
  }
  const credentialsPath = path.join(resolveStateDir(), "credentials", SIDECAR_KEY_NAME);
  const fromFile = await readSidecarKeyFile(credentialsPath);
  if (fromFile) {
    return fromFile;
  }
  if (process.platform === "darwin") {
    const fromKeychain = await readSidecarKeyFromKeychain();
    if (fromKeychain) {
      return fromKeychain;
    }
  }
  const keychainHint = process.platform === "darwin" ? " or the macOS keychain" : "";
  throw new Error(
    `missing sidecar API key: set ${SIDECAR_KEY_ENV} or write the key to ${credentialsPath}${keychainHint}`,
  );
}

async function readSidecarKeyFile(filePath: string): Promise<string | null> {
  try {
    const { buffer } = await readSecureFile({
      filePath,
      label: "rag sidecar api key",
      io: { maxBytes: 4096, timeoutMs: 5_000 },
    });
    return (
      buffer
        .toString("utf8")
        .replace(/^\uFEFF/, "")
        .trim() || null
    );
  } catch (err) {
    // Only a truly-absent file falls through to the next source. Other read errors
    // (e.g. insecure-permissions on a world-readable secret) are surfaced, not ignored.
    const missing =
      err instanceof FsSafeError
        ? err.code === "not-found"
        : (err as NodeJS.ErrnoException | undefined)?.code === "ENOENT";
    if (missing) {
      return null;
    }
    throw err;
  }
}

function readSidecarKeyFromKeychain(): Promise<string | null> {
  return new Promise<string | null>((resolve) => {
    execFile("security", ["find-generic-password", "-s", SIDECAR_KEY_NAME, "-w"], (err, stdout) => {
      resolve(err ? null : stdout.trim() || null);
    });
  });
}

function invalidParamsShape(
  method: string,
  errors: Parameters<typeof formatValidationErrors>[0],
): ErrorShape {
  return errorShape(
    ErrorCodes.INVALID_REQUEST,
    `invalid ${method} params: ${formatValidationErrors(errors)}`,
  );
}

async function sidecarRequest(
  requestPath: string,
  init: { method: "GET" | "POST"; body?: unknown },
) {
  const apiKey = await getSidecarApiKey();
  const res = await fetch(`${SIDECAR_URL}${requestPath}`, {
    method: init.method,
    headers: {
      authorization: `Bearer ${apiKey}`,
      ...(init.body === undefined ? {} : { "content-type": "application/json" }),
    },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
    signal: AbortSignal.timeout(SIDECAR_TIMEOUT_MS),
  });
  if (!res.ok) {
    throw new Error(`rag sidecar ${init.method} ${requestPath} failed: HTTP ${res.status}`);
  }
  return (await res.json()) as unknown;
}

/** Extracts the indexed chunk total from the ingest script stdout. */
function parseChunkTotal(stdout: string): number | undefined {
  const done = stdout.match(/Termine:\s*(\d+)\s+chunks/);
  if (done) {
    return Number(done[1]);
  }
  const perFile = stdout.match(/:\s*(\d+)\s+chunks indexes/);
  return perFile ? Number(perFile[1]) : undefined;
}

/** Drops the oldest finished jobs so the in-memory job list stays bounded. */
function pruneJobs(): void {
  if (ragJobs.size <= MAX_TRACKED_JOBS) {
    return;
  }
  const finished = [...ragJobs.values()]
    .filter((job) => job.status !== "running")
    .toSorted((a, b) => a.startedAt - b.startedAt);
  for (const job of finished) {
    if (ragJobs.size <= MAX_TRACKED_JOBS) {
      break;
    }
    ragJobs.delete(job.id);
  }
}

/** Runs the ingest pipeline detached from the request cycle and records the outcome. */
function startIngestJob(job: RagJob, filePath: string): void {
  const child = spawn("python3", [INGEST_SCRIPT, filePath], {
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (data: Buffer) => {
    stdout = (stdout + data.toString()).slice(0, MAX_CAPTURED_OUTPUT);
  });
  child.stderr.on("data", (data: Buffer) => {
    stderr = (stderr + data.toString()).slice(0, MAX_CAPTURED_OUTPUT);
  });
  const finish = (update: Pick<RagJob, "status"> & Partial<RagJob>) => {
    if (job.status !== "running") {
      return;
    }
    Object.assign(job, update, { finishedAt: Date.now() });
  };
  child.on("error", (err) => {
    finish({ status: "error", error: formatErrorMessage(err) });
  });
  child.on("close", (code) => {
    if (code === 0) {
      finish({ status: "done", chunks: parseChunkTotal(stdout) });
      return;
    }
    const detail = (stderr.trim() || stdout.trim()).slice(-500);
    finish({
      status: "error",
      error: `ingest exited with code ${code}${detail ? `: ${detail}` : ""}`,
    });
  });
}

type SidecarSearchResponse = {
  data?: Array<{
    score?: number;
    filename?: string;
    attributes?: { source?: unknown; pages?: unknown } | null;
    content?: Array<{ text?: string }>;
  }>;
};

type SidecarSourcesResponse = {
  sources?: Array<{ source?: string; chunks?: number; last_ingested?: string | null }>;
};

/** Gateway handlers for the local RAG ingest/search surface. */
export const ragHandlers: GatewayRequestHandlers = {
  "rag.ingest": async ({ params, respond }) => {
    if (!validateRagIngestParams(params)) {
      respond(false, undefined, invalidParamsShape("rag.ingest", validateRagIngestParams.errors));
      return;
    }
    // basename() neutralizes traversal segments; only the sanitized leaf name reaches disk.
    const fileName = path.basename(params.fileName.trim());
    const extension = path.extname(fileName).toLowerCase();
    if (
      !fileName ||
      fileName === "." ||
      fileName === ".." ||
      !SUPPORTED_EXTENSIONS.has(extension)
    ) {
      respond(
        false,
        undefined,
        errorShape(
          ErrorCodes.INVALID_REQUEST,
          `unsupported file name or extension: ${params.fileName} (allowed: ${[...SUPPORTED_EXTENSIONS].join(" ")})`,
        ),
      );
      return;
    }
    const data = Buffer.from(params.dataBase64, "base64");
    if (data.byteLength === 0) {
      respond(false, undefined, errorShape(ErrorCodes.INVALID_REQUEST, "empty document payload"));
      return;
    }
    try {
      await mkdir(INBOX_DIR, { recursive: true });
      const filePath = path.join(INBOX_DIR, fileName);
      await writeFile(filePath, data);
      const job: RagJob = {
        id: randomUUID(),
        fileName,
        status: "running",
        startedAt: Date.now(),
      };
      ragJobs.set(job.id, job);
      pruneJobs();
      startIngestJob(job, filePath);
      respond(true, { jobId: job.id }, undefined);
    } catch (err) {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, formatErrorMessage(err)));
    }
  },
  "rag.jobs": async ({ params, respond }) => {
    if (!validateRagJobsParams(params)) {
      respond(false, undefined, invalidParamsShape("rag.jobs", validateRagJobsParams.errors));
      return;
    }
    const jobs = [...ragJobs.values()].toSorted((a, b) => b.startedAt - a.startedAt);
    respond(true, { jobs }, undefined);
  },
  "rag.search": async ({ params, respond }) => {
    if (!validateRagSearchParams(params)) {
      respond(false, undefined, invalidParamsShape("rag.search", validateRagSearchParams.errors));
      return;
    }
    const topK = Math.min(params.topK ?? 5, 20);
    try {
      // Sidecar VectorStoreSearchRequest caps results via `limit` (litellm-pgvector models.py).
      const response = (await sidecarRequest(`/v1/vector_stores/${VECTOR_STORE_ID}/search`, {
        method: "POST",
        body: { query: params.query, limit: topK, max_num_results: topK, return_metadata: true },
      })) as SidecarSearchResponse;
      const results = (response.data ?? []).map((row) => {
        const attributes = row.attributes ?? {};
        const snippet = (row.content ?? [])
          .map((chunk) => chunk.text ?? "")
          .join(" ")
          .trim()
          .slice(0, 300);
        const pages = Array.isArray(attributes.pages)
          ? attributes.pages.filter((page): page is number => typeof page === "number")
          : [];
        const source =
          typeof attributes.source === "string" ? attributes.source : (row.filename ?? "unknown");
        return { score: row.score ?? 0, source, snippet, pages };
      });
      respond(true, { results }, undefined);
    } catch (err) {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, formatErrorMessage(err)));
    }
  },
  "rag.sources": async ({ params, respond }) => {
    if (!validateRagSourcesParams(params)) {
      respond(false, undefined, invalidParamsShape("rag.sources", validateRagSourcesParams.errors));
      return;
    }
    try {
      const response = (await sidecarRequest(`/v1/vector_stores/${VECTOR_STORE_ID}/sources`, {
        method: "GET",
      })) as SidecarSourcesResponse;
      const sources = (response.sources ?? []).map((entry) => ({
        source: entry.source ?? "unknown",
        chunks: entry.chunks ?? 0,
        // undefined is dropped by JSON serialization, matching the optional contract field.
        lastIngested: entry.last_ingested ?? undefined,
      }));
      respond(true, { sources }, undefined);
    } catch (err) {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, formatErrorMessage(err)));
    }
  },
};
