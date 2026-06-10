// Control UI view renders RAG screen content.
import { html, nothing } from "lit";
import { t } from "../../i18n/index.ts";
import type { RagJob, RagSearchResult, RagSource } from "../controllers/rag.ts";
import { RAG_ALLOWED_EXTENSIONS, RAG_MAX_FILE_BYTES } from "../controllers/rag.ts";

export type RagProps = {
  jobs: RagJob[];
  jobsLoading: boolean;
  sources: RagSource[];
  sourcesLoading: boolean;
  searchQuery: string;
  searchLoading: boolean;
  searchResults: RagSearchResult[] | null;
  uploadBusy: boolean;
  error: string | null;
  onFilesSelected: (files: FileList | null) => void;
  onRefreshJobs: () => void;
  onRefreshSources: () => void;
  onSearchQueryChange: (next: string) => void;
  onSearch: () => void;
};

function formatTimestamp(value?: string | number | null) {
  if (value == null || value === "") {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString();
}

function renderJobStatus(job: RagJob) {
  if (job.status === "running") {
    return html`<span class="muted">${t("rag.jobs.running")}</span>`;
  }
  if (job.status === "error") {
    return html`<span class="danger">✗ ${job.error ?? t("rag.jobs.failed")}</span>`;
  }
  return html`<span>✓ ${t("rag.jobs.chunks", { count: String(job.chunks ?? 0) })}</span>`;
}

function renderUploadCard(props: RagProps) {
  const maxMb = Math.floor(RAG_MAX_FILE_BYTES / (1024 * 1024));
  return html`
    <section class="card">
      <div class="card-title">${t("rag.upload.title")}</div>
      <div class="card-sub">
        ${t("rag.upload.subtitle", {
          extensions: RAG_ALLOWED_EXTENSIONS.join(" "),
          maxMb: String(maxMb),
        })}
      </div>
      <div class="row" style="gap: 8px; margin-top: 12px; flex-wrap: wrap;">
        <input
          type="file"
          multiple
          accept=${RAG_ALLOWED_EXTENSIONS.join(",")}
          ?disabled=${props.uploadBusy}
          @change=${(e: Event) => {
            const input = e.target as HTMLInputElement;
            props.onFilesSelected(input.files);
            input.value = "";
          }}
        />
        ${props.uploadBusy ? html`<span class="muted">${t("rag.upload.busy")}</span>` : nothing}
      </div>
    </section>
  `;
}

function renderJobsCard(props: RagProps) {
  return html`
    <section class="card" style="margin-top: 16px;">
      <div class="row" style="justify-content: space-between;">
        <div>
          <div class="card-title">${t("rag.jobs.title")}</div>
          <div class="card-sub">${t("rag.jobs.subtitle")}</div>
        </div>
        <button class="btn" ?disabled=${props.jobsLoading} @click=${props.onRefreshJobs}>
          ${props.jobsLoading ? t("common.loading") : t("common.refresh")}
        </button>
      </div>
      ${props.jobs.length === 0
        ? html`<div class="muted" style="margin-top: 12px;">${t("rag.jobs.empty")}</div>`
        : html`
            <table class="data-table" style="margin-top: 12px;">
              <thead>
                <tr>
                  <th>${t("rag.jobs.file")}</th>
                  <th>${t("rag.jobs.status")}</th>
                  <th>${t("rag.jobs.started")}</th>
                  <th>${t("rag.jobs.finished")}</th>
                </tr>
              </thead>
              <tbody>
                ${props.jobs.map(
                  (job) => html`
                    <tr>
                      <td>${job.fileName}</td>
                      <td>${renderJobStatus(job)}</td>
                      <td>${formatTimestamp(job.startedAt)}</td>
                      <td>${formatTimestamp(job.finishedAt)}</td>
                    </tr>
                  `,
                )}
              </tbody>
            </table>
          `}
    </section>
  `;
}

function renderSourcesCard(props: RagProps) {
  return html`
    <section class="card" style="margin-top: 16px;">
      <div class="row" style="justify-content: space-between;">
        <div>
          <div class="card-title">${t("rag.sources.title")}</div>
          <div class="card-sub">${t("rag.sources.subtitle")}</div>
        </div>
        <button class="btn" ?disabled=${props.sourcesLoading} @click=${props.onRefreshSources}>
          ${props.sourcesLoading ? t("common.loading") : t("common.refresh")}
        </button>
      </div>
      ${props.sources.length === 0
        ? html`<div class="muted" style="margin-top: 12px;">${t("rag.sources.empty")}</div>`
        : html`
            <table class="data-table" style="margin-top: 12px;">
              <thead>
                <tr>
                  <th>${t("rag.sources.source")}</th>
                  <th>${t("rag.sources.chunks")}</th>
                  <th>${t("rag.sources.lastIngested")}</th>
                </tr>
              </thead>
              <tbody>
                ${props.sources.map(
                  (source) => html`
                    <tr>
                      <td>${source.source}</td>
                      <td>${source.chunks}</td>
                      <td>${formatTimestamp(source.lastIngested)}</td>
                    </tr>
                  `,
                )}
              </tbody>
            </table>
          `}
    </section>
  `;
}

function renderSearchCard(props: RagProps) {
  return html`
    <section class="card" style="margin-top: 16px;">
      <div class="card-title">${t("rag.search.title")}</div>
      <div class="card-sub">${t("rag.search.subtitle")}</div>
      <div class="row" style="gap: 8px; margin-top: 12px;">
        <label class="field" style="flex: 1; min-width: 220px;">
          <input
            .value=${props.searchQuery}
            placeholder=${t("rag.search.placeholder")}
            @input=${(e: Event) => props.onSearchQueryChange((e.target as HTMLInputElement).value)}
            @keydown=${(e: KeyboardEvent) => {
              if (e.key === "Enter") {
                props.onSearch();
              }
            }}
          />
        </label>
        <button
          class="btn primary"
          ?disabled=${props.searchLoading || !props.searchQuery.trim()}
          @click=${props.onSearch}
        >
          ${props.searchLoading ? t("common.loading") : t("rag.search.button")}
        </button>
      </div>
      ${props.searchResults === null
        ? nothing
        : props.searchResults.length === 0
          ? html`<div class="muted" style="margin-top: 12px;">${t("rag.search.empty")}</div>`
          : props.searchResults.map(
              (result) => html`
                <div class="callout" style="margin-top: 12px;">
                  <div class="row" style="justify-content: space-between; flex-wrap: wrap;">
                    <strong>${result.source}</strong>
                    <span class="mono">
                      ${t("rag.search.score", { score: result.score.toFixed(3) })}
                    </span>
                  </div>
                  <div style="margin-top: 6px;">${result.snippet}</div>
                  ${result.pages.length > 0
                    ? html`
                        <div class="muted" style="margin-top: 6px;">
                          ${t("rag.search.pages", { pages: result.pages.join(", ") })}
                        </div>
                      `
                    : nothing}
                </div>
              `,
            )}
    </section>
  `;
}

export function renderRag(props: RagProps) {
  return html`
    ${props.error
      ? html`<div class="callout danger" style="margin-bottom: 12px;">${props.error}</div>`
      : nothing}
    ${renderUploadCard(props)} ${renderJobsCard(props)} ${renderSourcesCard(props)}
    ${renderSearchCard(props)}
  `;
}
