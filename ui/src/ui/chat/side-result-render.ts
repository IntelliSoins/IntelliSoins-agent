// Control UI chat module implements side result render behavior.
import { html, nothing, type TemplateResult } from "lit";
import { unsafeHTML } from "lit/directives/unsafe-html.js";
import { t } from "../../i18n/index.ts";
import { icons } from "../icons.ts";
import { toSanitizedMarkdownHtml } from "../markdown.ts";
import { detectTextDirection } from "../text-direction.ts";
import type { ChatSideResult } from "./side-result.ts";

export function renderSideResult(
  sideResult: ChatSideResult | null | undefined,
  onDismiss?: () => void,
): TemplateResult | typeof nothing {
  if (!sideResult) {
    return nothing;
  }
  return html`
    <section
      class=${`chat-side-result ${sideResult.isError ? "chat-side-result--error" : ""}`}
      role="status"
      aria-live="polite"
      aria-label=${t("sideResult.ariaLabel")}
    >
      <div class="chat-side-result__header">
        <div class="chat-side-result__label-row">
          <span class="chat-side-result__label">${t("sideResult.label")}</span>
          <span class="chat-side-result__meta">${t("sideResult.notSaved")}</span>
        </div>
        <button
          class="btn chat-side-result__dismiss"
          type="button"
          aria-label=${t("sideResult.dismissAria")}
          title=${t("sideResult.dismiss")}
          @click=${() => onDismiss?.()}
        >
          ${icons.x}
        </button>
      </div>
      <div class="chat-side-result__question">${sideResult.question}</div>
      <div class="chat-side-result__body" dir=${detectTextDirection(sideResult.text)}>
        ${unsafeHTML(toSanitizedMarkdownHtml(sideResult.text))}
      </div>
    </section>
  `;
}
