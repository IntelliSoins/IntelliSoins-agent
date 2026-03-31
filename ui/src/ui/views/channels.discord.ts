import { html, nothing } from "lit";
import { formatRelativeTimestamp } from "../format.ts";
import type { DiscordStatus } from "../types.ts";
import { renderChannelConfigSection } from "./channels.config.ts";
import type { ChannelsProps } from "./channels.types.ts";

export function renderDiscordCard(params: {
  props: ChannelsProps;
  discord?: DiscordStatus | null;
  accountCountLabel: unknown;
}) {
  const { props, discord, accountCountLabel } = params;

  return html`
    <div class="card">
      <div class="card-title">Discord</div>
      <div class="card-sub">État du bot et configuration du canal.</div>
      ${accountCountLabel}

      <div class="status-list" style="margin-top: 16px;">
        <div>
          <span class="label">Configuré</span>
          <span>${discord?.configured ? "Oui" : "Non"}</span>
        </div>
        <div>
          <span class="label">En cours</span>
          <span>${discord?.running ? "Oui" : "Non"}</span>
        </div>
        <div>
          <span class="label">Dernier démarrage</span>
          <span>${discord?.lastStartAt ? formatRelativeTimestamp(discord.lastStartAt) : "n/d"}</span>
        </div>
        <div>
          <span class="label">Dernière vérification</span>
          <span>${discord?.lastProbeAt ? formatRelativeTimestamp(discord.lastProbeAt) : "n/d"}</span>
        </div>
      </div>

      ${
        discord?.lastError
          ? html`<div class="callout danger" style="margin-top: 12px;">
            ${discord.lastError}
          </div>`
          : nothing
      }

      ${
        discord?.probe
          ? html`<div class="callout" style="margin-top: 12px;">
            Probe ${discord.probe.ok ? "ok" : "failed"} ·
            ${discord.probe.status ?? ""} ${discord.probe.error ?? ""}
          </div>`
          : nothing
      }

      ${renderChannelConfigSection({ channelId: "discord", props })}

      <div class="row" style="margin-top: 12px;">
        <button class="btn" @click=${() => props.onRefresh(true)}>
          Vérifier
        </button>
      </div>
    </div>
  `;
}
