import { html, nothing } from "lit";
import { formatRelativeTimestamp } from "../format.ts";
import type { SlackStatus } from "../types.ts";
import { renderChannelConfigSection } from "./channels.config.ts";
import type { ChannelsProps } from "./channels.types.ts";

export function renderSlackCard(params: {
  props: ChannelsProps;
  slack?: SlackStatus | null;
  accountCountLabel: unknown;
}) {
  const { props, slack, accountCountLabel } = params;

  return html`
    <div class="card">
      <div class="card-title">Slack</div>
      <div class="card-sub">État du mode socket et configuration du canal.</div>
      ${accountCountLabel}

      <div class="status-list" style="margin-top: 16px;">
        <div>
          <span class="label">Configuré</span>
          <span>${slack?.configured ? "Oui" : "Non"}</span>
        </div>
        <div>
          <span class="label">En cours</span>
          <span>${slack?.running ? "Oui" : "Non"}</span>
        </div>
        <div>
          <span class="label">Dernier démarrage</span>
          <span>${slack?.lastStartAt ? formatRelativeTimestamp(slack.lastStartAt) : "n/d"}</span>
        </div>
        <div>
          <span class="label">Dernière vérification</span>
          <span>${slack?.lastProbeAt ? formatRelativeTimestamp(slack.lastProbeAt) : "n/d"}</span>
        </div>
      </div>

      ${
        slack?.lastError
          ? html`<div class="callout danger" style="margin-top: 12px;">
            ${slack.lastError}
          </div>`
          : nothing
      }

      ${
        slack?.probe
          ? html`<div class="callout" style="margin-top: 12px;">
            Probe ${slack.probe.ok ? "ok" : "failed"} ·
            ${slack.probe.status ?? ""} ${slack.probe.error ?? ""}
          </div>`
          : nothing
      }

      ${renderChannelConfigSection({ channelId: "slack", props })}

      <div class="row" style="margin-top: 12px;">
        <button class="btn" @click=${() => props.onRefresh(true)}>
          Vérifier
        </button>
      </div>
    </div>
  `;
}
