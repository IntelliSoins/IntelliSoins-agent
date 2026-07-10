// Control UI view renders agent workspace config files as editable form fields.
import { html, nothing } from "lit";
import { t } from "../../i18n/index.ts";
import {
  applyAgentFileFormChange,
  buildAgentFileMarkdownFromForm,
  parseAgentFileMarkdown,
  type AgentFileFormModel,
} from "../agent-file-markdown.ts";
import { icons } from "../icons.ts";

export type AgentFileFormProps = {
  fileName: string;
  baseContent: string;
  draft: string;
  saving?: boolean;
  missing?: boolean;
  showRaw?: boolean;
  compact?: boolean;
  onDraftChange: (content: string) => void;
  onSave: () => void;
  onReset: () => void;
  onToggleRaw?: () => void;
};

function resolveFieldHint(hintKey: string | undefined): string | undefined {
  if (!hintKey) {
    return undefined;
  }
  return t(hintKey);
}

function renderFormField(
  model: AgentFileFormModel,
  field: AgentFileFormModel["fields"][number],
  onModelChange: (next: AgentFileFormModel) => void,
) {
  const hint = resolveFieldHint(field.hint);
  const control =
    field.kind === "text"
      ? html`<input
          type="text"
          .value=${field.value}
          @input=${(event: Event) => {
            const value = (event.target as HTMLInputElement).value;
            onModelChange(applyAgentFileFormChange(model, { type: "field", id: field.id, value }));
          }}
        />`
      : html`<textarea
          class="agent-config-form__textarea"
          .value=${field.value}
          @input=${(event: Event) => {
            const value = (event.target as HTMLTextAreaElement).value;
            onModelChange(applyAgentFileFormChange(model, { type: "field", id: field.id, value }));
          }}
        ></textarea>`;

  return html`
    <label class="field agent-config-form__field">
      <span>${field.label}</span>
      ${hint ? html`<span class="agent-config-form__hint">${hint}</span>` : nothing} ${control}
    </label>
  `;
}

function renderFormSection(
  model: AgentFileFormModel,
  section: AgentFileFormModel["sections"][number],
  onModelChange: (next: AgentFileFormModel) => void,
) {
  return html`
    <section class="agent-config-form__section">
      <div class="agent-config-form__section-title">${section.title}</div>
      <label class="field agent-config-form__field">
        <textarea
          class="agent-config-form__textarea"
          .value=${section.value}
          @input=${(event: Event) => {
            const value = (event.target as HTMLTextAreaElement).value;
            onModelChange(
              applyAgentFileFormChange(model, { type: "section", id: section.id, value }),
            );
          }}
        ></textarea>
      </label>
    </section>
  `;
}

function renderRawEditor(props: AgentFileFormProps) {
  return html`
    <label class="field agent-config-form__field agent-config-form__field--raw">
      <span>${t("agents.files.content")}</span>
      <textarea
        class="agent-file-textarea"
        .value=${props.draft}
        @input=${(event: Event) => props.onDraftChange((event.target as HTMLTextAreaElement).value)}
      ></textarea>
    </label>
  `;
}

export function renderAgentFileForm(props: AgentFileFormProps) {
  const isDirty = props.draft !== props.baseContent;
  const model = parseAgentFileMarkdown(props.fileName, props.draft);
  const displayName = props.fileName.replace(/\.md$/i, "");

  const handleModelChange = (nextModel: AgentFileFormModel) => {
    props.onDraftChange(buildAgentFileMarkdownFromForm(nextModel));
  };

  return html`
    <div class="agent-config-form ${props.compact ? "agent-config-form--compact" : ""}">
      <div class="agent-config-form__header">
        <div>
          <div class="agent-config-form__title">${displayName}</div>
          <div class="agent-config-form__subtitle">${t("agentFileForm.subtitle")}</div>
        </div>
        <div class="agent-file-actions">
          ${props.onToggleRaw
            ? html`
                <button class="btn btn--sm" type="button" @click=${props.onToggleRaw}>
                  ${props.showRaw ? t("agentFileForm.useForm") : t("agentFileForm.editRaw")}
                </button>
              `
            : nothing}
          <button class="btn btn--sm" type="button" ?disabled=${!isDirty} @click=${props.onReset}>
            ${t("common.reset")}
          </button>
          <button
            class="btn btn--sm primary"
            type="button"
            ?disabled=${props.saving || !isDirty}
            @click=${props.onSave}
          >
            ${props.saving ? t("common.saving") : t("common.save")}
          </button>
        </div>
      </div>

      ${props.missing
        ? html`<div class="callout info agent-config-form__notice">
            ${t("agents.files.missingHint")}
          </div>`
        : nothing}
      ${isDirty
        ? html`<div class="agent-config-form__dirty">${t("agentFileForm.unsavedChanges")}</div>`
        : nothing}
      ${props.showRaw
        ? renderRawEditor(props)
        : html`
            <div class="agent-config-form__body">
              ${model.fields.length > 0
                ? html`
                    <section class="agent-config-form__group">
                      <div class="agent-config-form__group-title">
                        ${t("agentFileForm.details")}
                      </div>
                      ${model.fields.map((field) =>
                        renderFormField(model, field, handleModelChange),
                      )}
                    </section>
                  `
                : nothing}
              ${model.sections.length > 0
                ? html`
                    <section class="agent-config-form__group">
                      ${model.sections.map((section) =>
                        renderFormSection(model, section, handleModelChange),
                      )}
                    </section>
                  `
                : nothing}
              ${model.fields.length === 0 && model.sections.length === 0
                ? html`<div class="muted agent-config-form__empty">
                    ${t("agentFileForm.emptyStructure")}
                  </div>`
                : nothing}
            </div>
          `}
    </div>
  `;
}

export type AgentFileSidebarProps = {
  fileName: string;
  baseContent: string;
  draft: string;
  saving?: boolean;
  missing?: boolean;
  error?: string | null;
  showRaw?: boolean;
  onClose: () => void;
  onDraftChange: (content: string) => void;
  onSave: () => void;
  onReset: () => void;
  onToggleRaw?: () => void;
};

export function renderAgentFileSidebar(props: AgentFileSidebarProps) {
  return html`
    <div class="sidebar-panel agent-file-sidebar">
      <div class="sidebar-header">
        <div class="sidebar-title">${props.fileName.replace(/\.md$/i, "")}</div>
        <button
          @click=${props.onClose}
          class="btn"
          type="button"
          title=${t("markdownSidebar.closeSidebar")}
          aria-label=${t("markdownSidebar.closeSidebar")}
        >
          ${icons.x}
        </button>
      </div>
      <div class="sidebar-content agent-file-sidebar__content">
        ${props.error ? html`<div class="callout danger">${props.error}</div>` : nothing}
        ${renderAgentFileForm({
          fileName: props.fileName,
          baseContent: props.baseContent,
          draft: props.draft,
          saving: props.saving,
          missing: props.missing,
          showRaw: props.showRaw,
          compact: true,
          onDraftChange: props.onDraftChange,
          onSave: props.onSave,
          onReset: props.onReset,
          onToggleRaw: props.onToggleRaw,
        })}
      </div>
    </div>
  `;
}
