// Control UI codec converts agent workspace markdown files to editable form fields.

export const EDITABLE_AGENT_CONFIG_FILES = new Set([
  "AGENTS.md",
  "SOUL.md",
  "TOOLS.md",
  "IDENTITY.md",
  "USER.md",
  "HEARTBEAT.md",
  "BOOTSTRAP.md",
  "MEMORY.md",
]);

export type AgentFileFieldKind = "text" | "textarea";

export type AgentFileFormField = {
  id: string;
  label: string;
  kind: AgentFileFieldKind;
  hint?: string;
  value: string;
};

export type AgentFileFormSection = {
  id: string;
  title: string;
  value: string;
};

export type AgentFileFormModel = {
  fileName: string;
  frontmatter: string;
  preamble: string;
  fields: AgentFileFormField[];
  sections: AgentFileFormSection[];
  epilogue: string;
};

const FIELD_HINTS: Record<string, Record<string, string>> = {
  "IDENTITY.md": {
    Name: "agentFileForm.hints.identity.name",
    Creature: "agentFileForm.hints.identity.creature",
    Vibe: "agentFileForm.hints.identity.vibe",
    Emoji: "agentFileForm.hints.identity.emoji",
    Avatar: "agentFileForm.hints.identity.avatar",
  },
  "USER.md": {
    Name: "agentFileForm.hints.user.name",
    "What to call them": "agentFileForm.hints.user.whatToCallThem",
    "Preferred address": "agentFileForm.hints.user.whatToCallThem",
    Pronouns: "agentFileForm.hints.user.pronouns",
    Timezone: "agentFileForm.hints.user.timezone",
    Notes: "agentFileForm.hints.user.notes",
    Context: "agentFileForm.hints.user.context",
  },
  "SOUL.md": {
    "Core Truths": "agentFileForm.hints.soul.coreTruths",
    Boundaries: "agentFileForm.hints.soul.boundaries",
    Vibe: "agentFileForm.hints.soul.vibe",
    Continuity: "agentFileForm.hints.soul.continuity",
  },
};

const TEXT_FIELD_LABELS = new Set([
  "Name",
  "Creature",
  "Emoji",
  "Avatar",
  "Pronouns",
  "Timezone",
  "What to call them",
  "Preferred address",
]);

function slugifyLabel(label: string): string {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function splitFrontmatter(content: string): { frontmatter: string; body: string } {
  if (!content.startsWith("---\n")) {
    return { frontmatter: "", body: content };
  }
  const end = content.indexOf("\n---\n", 4);
  if (end === -1) {
    return { frontmatter: "", body: content };
  }
  return {
    frontmatter: content.slice(0, end + 5),
    body: content.slice(end + 5).replace(/^\n/, ""),
  };
}

function isRelatedSection(title: string): boolean {
  return title.trim().toLowerCase() === "related";
}

function findFirstBulletFieldIndex(lines: string[]): number {
  return lines.findIndex((line) => /^- \*\*(.+?):\*\*/.test(line));
}

function normalizeBulletFieldValue(value: string): string {
  return trimTrailingBlankLines(
    value
      .split("\n")
      .map((line) => line.replace(/^\s{2}/, ""))
      .join("\n")
      .trim(),
  );
}

function parseBulletFields(text: string): {
  fields: Array<{ label: string; value: string }>;
  preamble: string;
  remainder: string;
} {
  const lines = text.split("\n");
  const firstBulletIndex = findFirstBulletFieldIndex(lines);
  if (firstBulletIndex === -1) {
    return { fields: [], preamble: text.trim(), remainder: "" };
  }
  const preamble = lines.slice(0, firstBulletIndex).join("\n").trim();
  const fields: Array<{ label: string; value: string }> = [];
  let index = firstBulletIndex;
  while (index < lines.length) {
    const match = lines[index]?.match(/^- \*\*(.+?):\*\*\s*(.*)$/);
    if (!match) {
      break;
    }
    const label = match[1]?.trim() ?? "";
    const inlineValue = match[2]?.trim() ?? "";
    index += 1;
    const valueLines: string[] = [];
    if (inlineValue) {
      valueLines.push(inlineValue);
    }
    while (index < lines.length) {
      const line = lines[index] ?? "";
      if (/^- \*\*.+?:\*\*/.test(line) || line.startsWith("## ") || /^---\s*$/.test(line)) {
        break;
      }
      valueLines.push(line);
      index += 1;
    }
    fields.push({
      label,
      value: normalizeBulletFieldValue(valueLines.join("\n")),
    });
  }
  return {
    fields,
    preamble,
    remainder: lines.slice(index).join("\n"),
  };
}

function trimTrailingBlankLines(value: string): string {
  const lines = value.split("\n");
  while (lines.length > 0 && lines[lines.length - 1]?.trim() === "") {
    lines.pop();
  }
  return lines.join("\n");
}

function parseSections(text: string): {
  preamble: string;
  sections: Array<{ title: string; value: string }>;
  epilogue: string;
} {
  const normalized = text.trim();
  if (!normalized) {
    return { preamble: "", sections: [], epilogue: "" };
  }
  const splitTarget = normalized.startsWith("## ") ? `\n${normalized}` : normalized;
  const parts = splitTarget.split(/\n(?=## )/);
  const preamble = (parts[0] ?? "").trim();
  const sections: Array<{ title: string; value: string }> = [];
  const epilogueParts: string[] = [];
  for (let i = 1; i < parts.length; i += 1) {
    const chunk = parts[i] ?? "";
    const titleMatch = chunk.match(/^## (.+?)(?:\n|$)/);
    if (!titleMatch) {
      epilogueParts.push(chunk);
      continue;
    }
    const title = titleMatch[1]?.trim() ?? "";
    const value = chunk.slice(titleMatch[0].length).replace(/^\n/, "");
    if (isRelatedSection(title)) {
      epilogueParts.push(`## ${title}${value ? `\n${value}` : ""}`);
      continue;
    }
    sections.push({ title, value: trimTrailingBlankLines(value) });
  }
  return {
    preamble,
    sections,
    epilogue: epilogueParts.join("\n\n").trim(),
  };
}

function resolveFieldKind(fileName: string, label: string): AgentFileFieldKind {
  if (TEXT_FIELD_LABELS.has(label)) {
    return "text";
  }
  if (fileName === "USER.md" && label === "Notes") {
    return "textarea";
  }
  return "textarea";
}

function resolveFieldHint(fileName: string, label: string): string | undefined {
  return FIELD_HINTS[fileName]?.[label];
}

function toFormField(fileName: string, label: string, value: string): AgentFileFormField {
  return {
    id: slugifyLabel(label),
    label,
    kind: resolveFieldKind(fileName, label),
    hint: resolveFieldHint(fileName, label),
    value,
  };
}

function toFormSection(title: string, value: string): AgentFileFormSection {
  return {
    id: slugifyLabel(title),
    title,
    value,
  };
}

export function isEditableAgentConfigFile(fileName: string): boolean {
  return EDITABLE_AGENT_CONFIG_FILES.has(fileName);
}

export function parseAgentFileMarkdown(fileName: string, content: string): AgentFileFormModel {
  const { frontmatter, body } = splitFrontmatter(content);
  const bulletParsed = parseBulletFields(body);
  const sectionSource = bulletParsed.fields.length > 0 ? bulletParsed.remainder : body;
  const sectionParsed = parseSections(sectionSource);
  const fields = bulletParsed.fields.map((field) =>
    toFormField(fileName, field.label, field.value),
  );
  const sections = sectionParsed.sections.map((section) =>
    toFormSection(section.title, section.value),
  );
  const preamble = joinBlocks([
    bulletParsed.fields.length > 0 ? bulletParsed.preamble : sectionParsed.preamble,
  ]);

  return {
    fileName,
    frontmatter,
    preamble,
    fields,
    sections,
    epilogue: sectionParsed.epilogue,
  };
}

function serializeBulletFields(fields: AgentFileFormField[]): string {
  if (fields.length === 0) {
    return "";
  }
  return fields
    .map((field) => {
      const value = field.value.trim();
      if (!value) {
        return `- **${field.label}:**`;
      }
      const lines = value.split("\n");
      const [first, ...rest] = lines;
      const head = `- **${field.label}:** ${first ?? ""}`.trimEnd();
      if (rest.length === 0) {
        return head;
      }
      return [head, ...rest.map((line) => (line.length > 0 ? `  ${line}` : ""))].join("\n");
    })
    .join("\n");
}

function serializeSections(sections: AgentFileFormSection[]): string {
  return sections
    .map((section) => {
      const value = section.value.trim();
      return value ? `## ${section.title}\n\n${value}` : `## ${section.title}`;
    })
    .join("\n\n");
}

function joinBlocks(blocks: Array<string | undefined>): string {
  return blocks
    .map((block) => block?.trim() ?? "")
    .filter((block) => block.length > 0)
    .join("\n\n");
}

export function serializeAgentFileMarkdown(model: AgentFileFormModel): string {
  const body = joinBlocks([
    model.preamble,
    serializeBulletFields(model.fields),
    serializeSections(model.sections),
    model.epilogue,
  ]);
  if (!model.frontmatter.trim()) {
    return body;
  }
  return model.frontmatter.endsWith("\n")
    ? `${model.frontmatter}${body}`
    : `${model.frontmatter}\n${body}`;
}

export function applyAgentFileFormChange(
  model: AgentFileFormModel,
  change:
    | { type: "field"; id: string; value: string }
    | { type: "section"; id: string; value: string },
): AgentFileFormModel {
  if (change.type === "field") {
    return {
      ...model,
      fields: model.fields.map((field) =>
        field.id === change.id ? { ...field, value: change.value } : field,
      ),
    };
  }
  return {
    ...model,
    sections: model.sections.map((section) =>
      section.id === change.id ? { ...section, value: change.value } : section,
    ),
  };
}

export function buildAgentFileMarkdownFromForm(model: AgentFileFormModel): string {
  return serializeAgentFileMarkdown(model);
}
