// Control UI view renders mcp screen content.
import { redactSensitiveUrlLikeString } from "@openclaw/net-policy/redact-sensitive-url";
import { html, nothing, type TemplateResult } from "lit";
import { t } from "../../i18n/index.ts";

type McpServerRow = {
  name: string;
  enabled: boolean;
  transport: "stdio" | "http" | "invalid";
  auth: string | null;
  launch: string;
  toolFilter: boolean;
  parallel: boolean;
  tls: string | null;
};

export type McpViewProps = {
  configObject: Record<string, unknown>;
  configDirty: boolean;
  configSaving: boolean;
  configApplying: boolean;
  connected: boolean;
  onSaveConfig: () => void;
  onApplyConfig: () => void;
  onServerEnabledChange: (name: string, enabled: boolean) => void;
  editor: TemplateResult;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function getMcpServers(configObject: Record<string, unknown>): Record<string, unknown> {
  return asRecord(asRecord(configObject.mcp)?.servers) ?? {};
}

function summarizeServer(name: string, value: unknown): McpServerRow {
  const server = asRecord(value) ?? {};
  const url = typeof server.url === "string" ? server.url : "";
  const command = typeof server.command === "string" ? server.command : "";
  const transport = url ? "http" : command ? "stdio" : "invalid";
  const auth = typeof server.auth === "string" ? server.auth : null;
  const launch = url || command || t("mcpPage.servers.missingTransport");
  const tls =
    server.sslVerify === false
      ? t("mcpPage.servers.tlsVerifyOff")
      : server.clientCert || server.clientKey
        ? t("mcpPage.servers.mtls")
        : null;
  return {
    name,
    enabled: server.enabled !== false,
    transport,
    auth,
    launch: url ? redactSensitiveUrlLikeString(launch) : launch,
    toolFilter: Boolean(server.toolFilter),
    parallel: server.supportsParallelToolCalls === true,
    tls,
  };
}

function quoteShellArg(value: string): string {
  return /^[A-Za-z0-9._:/-]+$/.test(value) ? value : `'${value.replaceAll("'", "'\\''")}'`;
}

function renderServerRow(props: McpViewProps, server: McpServerRow) {
  const quotedName = quoteShellArg(server.name);
  const probeCommand = `intellisoins mcp probe ${quotedName}`;
  const loginCommand = `intellisoins mcp login ${quotedName}`;
  return html`
    <article class="mcp-server-row">
      <div class="mcp-server-row__main">
        <div class="mcp-server-row__title">
          <span>${server.name}</span>
          <span class="pill pill--sm ${server.enabled ? "pill--ok" : ""}">
            ${server.enabled ? t("common.enabled") : t("common.disabled")}
          </span>
        </div>
        <div class="mcp-server-row__launch">${server.launch}</div>
        <div class="mcp-server-row__meta">
          <span>${server.transport}</span>
          ${server.auth ? html`<span>${server.auth}</span>` : nothing}
          ${server.toolFilter ? html`<span>${t("mcpPage.servers.toolFilter")}</span>` : nothing}
          ${server.parallel ? html`<span>${t("mcpPage.servers.parallel")}</span>` : nothing}
          ${server.tls ? html`<span>${server.tls}</span>` : nothing}
        </div>
      </div>
      <div class="mcp-server-row__actions">
        <button
          class="btn btn--sm"
          ?disabled=${props.configSaving}
          @click=${() => props.onServerEnabledChange(server.name, !server.enabled)}
        >
          ${server.enabled ? t("mcpPage.servers.disable") : t("mcpPage.servers.enable")}
        </button>
        <code>${server.auth === "oauth" ? loginCommand : probeCommand}</code>
      </div>
    </article>
  `;
}

export function renderMcp(props: McpViewProps) {
  const rows = Object.entries(getMcpServers(props.configObject))
    .map(([name, server]) => summarizeServer(name, server))
    .toSorted((a, b) => a.name.localeCompare(b.name));
  const enabledCount = rows.filter((row) => row.enabled).length;
  const oauthCount = rows.filter((row) => row.auth === "oauth").length;
  const filteredCount = rows.filter((row) => row.toolFilter).length;
  const saveDisabled =
    !props.configDirty || !props.connected || props.configApplying || props.configSaving;
  return html`
    <section class="mcp-page">
      <div class="mcp-page__summary">
        <div class="stat">
          <div class="stat-label">${t("mcpPage.stats.servers")}</div>
          <div class="stat-value">${rows.length}</div>
        </div>
        <div class="stat">
          <div class="stat-label">${t("mcpPage.stats.enabled")}</div>
          <div class="stat-value ${enabledCount === rows.length ? "ok" : "warn"}">
            ${enabledCount}
          </div>
        </div>
        <div class="stat">
          <div class="stat-label">${t("mcpPage.stats.oauth")}</div>
          <div class="stat-value">${oauthCount}</div>
        </div>
        <div class="stat">
          <div class="stat-label">${t("mcpPage.stats.filtered")}</div>
          <div class="stat-value">${filteredCount}</div>
        </div>
      </div>

      <section class="card mcp-command-card">
        <div>
          <div class="card-title">${t("mcpPage.commands.title")}</div>
          <div class="card-sub">${t("mcpPage.commands.subtitle")}</div>
        </div>
        <div class="mcp-command-card__grid">
          <code>intellisoins mcp status --verbose</code>
          <code>intellisoins mcp doctor --probe</code>
          <code>intellisoins mcp login &lt;name&gt;</code>
          <code>intellisoins mcp reload</code>
        </div>
      </section>

      <section class="card mcp-server-list">
        <div class="mcp-server-list__header">
          <div>
            <div class="card-title">${t("mcpPage.servers.title")}</div>
            <div class="card-sub">${t("mcpPage.servers.subtitle")}</div>
          </div>
          <div class="mcp-server-list__actions">
            <button class="btn btn--sm" ?disabled=${saveDisabled} @click=${props.onSaveConfig}>
              ${t("common.save")}
            </button>
            <button
              class="btn btn--sm primary"
              ?disabled=${!props.configDirty ||
              !props.connected ||
              props.configApplying ||
              props.configSaving}
              @click=${props.onApplyConfig}
            >
              ${props.configApplying ? t("mcpPage.publishing") : t("common.saveAndPublish")}
            </button>
          </div>
        </div>
        ${rows.length
          ? html`<div class="mcp-server-list__rows">
              ${rows.map((row) => renderServerRow(props, row))}
            </div>`
          : html`<div class="data-table-empty-state">${t("mcpPage.servers.empty")}</div>`}
      </section>

      ${props.editor}
    </section>
  `;
}
