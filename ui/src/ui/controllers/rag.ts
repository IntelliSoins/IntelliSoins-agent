// Control UI controller manages RAG gateway state.
import { t } from "../../i18n/index.ts";
import type { GatewayBrowserClient } from "../gateway.ts";

export type RagJobStatus = "running" | "done" | "error";

export type RagJob = {
  id: string;
  fileName: string;
  status: RagJobStatus;
  chunks?: number;
  error?: string;
  startedAt: string | number;
  finishedAt?: string | number;
};

export type RagSource = {
  source: string;
  chunks: number;
  lastIngested?: string;
};

export type RagSearchResult = {
  score: number;
  source: string;
  snippet: string;
  pages: number[];
};

export type RagState = {
  client: GatewayBrowserClient | null;
  connected: boolean;
  ragJobs: RagJob[];
  ragJobsLoading: boolean;
  ragSources: RagSource[];
  ragSourcesLoading: boolean;
  ragSearchQuery: string;
  ragSearchLoading: boolean;
  ragSearchResults: RagSearchResult[] | null;
  ragUploadBusy: boolean;
  ragError: string | null;
  ragJobsPollTimer: number | ReturnType<typeof globalThis.setInterval> | null;
};

export const RAG_MAX_FILE_BYTES = 6 * 1024 * 1024;
export const RAG_ALLOWED_EXTENSIONS = [
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
] as const;

// Poll only while a job is running; the gateway has no job push events.
const RAG_JOBS_POLL_MS = 2500;

function hasAllowedRagExtension(fileName: string): boolean {
  const lowered = fileName.toLowerCase();
  return RAG_ALLOWED_EXTENSIONS.some((ext) => lowered.endsWith(ext));
}

function encodeBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  // Chunked conversion keeps the argument list under engine call limits.
  const chunkSize = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

export function stopRagJobsPolling(state: RagState) {
  if (state.ragJobsPollTimer == null) {
    return;
  }
  globalThis.clearInterval(state.ragJobsPollTimer);
  state.ragJobsPollTimer = null;
}

function syncRagJobsPolling(state: RagState) {
  const hasRunning = state.ragJobs.some((job) => job.status === "running");
  if (!hasRunning) {
    stopRagJobsPolling(state);
    return;
  }
  if (state.ragJobsPollTimer != null) {
    return;
  }
  state.ragJobsPollTimer = globalThis.setInterval(() => {
    void loadRagJobs(state, { quiet: true });
  }, RAG_JOBS_POLL_MS);
}

export async function loadRagJobs(state: RagState, opts?: { quiet?: boolean }) {
  if (!state.client || !state.connected) {
    stopRagJobsPolling(state);
    return;
  }
  if (opts?.quiet !== true) {
    state.ragJobsLoading = true;
  }
  try {
    const res = await state.client.request<{ jobs?: RagJob[] }>("rag.jobs", {});
    const hadRunning = state.ragJobs.some((job) => job.status === "running");
    state.ragJobs = Array.isArray(res?.jobs) ? res.jobs : [];
    state.ragError = null;
    const hasRunning = state.ragJobs.some((job) => job.status === "running");
    if (hadRunning && !hasRunning) {
      void loadRagSources(state);
    }
  } catch (err) {
    state.ragError = String(err);
  } finally {
    if (opts?.quiet !== true) {
      state.ragJobsLoading = false;
    }
    syncRagJobsPolling(state);
  }
}

export async function loadRagSources(state: RagState) {
  if (!state.client || !state.connected) {
    return;
  }
  state.ragSourcesLoading = true;
  try {
    const res = await state.client.request<{ sources?: RagSource[] }>("rag.sources", {});
    state.ragSources = Array.isArray(res?.sources) ? res.sources : [];
    state.ragError = null;
  } catch (err) {
    state.ragError = String(err);
  } finally {
    state.ragSourcesLoading = false;
  }
}

export async function searchRag(state: RagState, topK = 8) {
  const query = state.ragSearchQuery.trim();
  if (!state.client || !state.connected || !query || state.ragSearchLoading) {
    return;
  }
  state.ragSearchLoading = true;
  try {
    const res = await state.client.request<{ results?: RagSearchResult[] }>("rag.search", {
      query,
      topK,
    });
    state.ragSearchResults = Array.isArray(res?.results) ? res.results : [];
    state.ragError = null;
  } catch (err) {
    state.ragError = String(err);
  } finally {
    state.ragSearchLoading = false;
  }
}

export async function ingestRagFiles(state: RagState, files: FileList | null) {
  if (!state.client || !state.connected || state.ragUploadBusy || !files || files.length === 0) {
    return;
  }
  const maxMb = Math.floor(RAG_MAX_FILE_BYTES / (1024 * 1024));
  const rejected: string[] = [];
  const accepted: File[] = [];
  for (const file of files) {
    if (!hasAllowedRagExtension(file.name)) {
      rejected.push(t("rag.upload.unsupportedType", { fileName: file.name }));
    } else if (file.size > RAG_MAX_FILE_BYTES) {
      rejected.push(t("rag.upload.fileTooLarge", { fileName: file.name, maxMb: String(maxMb) }));
    } else {
      accepted.push(file);
    }
  }
  state.ragError = rejected.length > 0 ? rejected.join(" ") : null;
  if (accepted.length === 0) {
    return;
  }
  state.ragUploadBusy = true;
  try {
    for (const file of accepted) {
      const dataBase64 = encodeBase64(await file.arrayBuffer());
      await state.client.request<{ jobId: string }>("rag.ingest", {
        fileName: file.name,
        dataBase64,
      });
    }
  } catch (err) {
    state.ragError = String(err);
  } finally {
    state.ragUploadBusy = false;
  }
  await loadRagJobs(state, { quiet: true });
}
