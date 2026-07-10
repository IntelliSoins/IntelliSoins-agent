// Control UI tests cover agent workspace markdown form codec behavior.
import { describe, expect, it } from "vitest";
import {
  applyAgentFileFormChange,
  buildAgentFileMarkdownFromForm,
  isEditableAgentConfigFile,
  parseAgentFileMarkdown,
  serializeAgentFileMarkdown,
} from "./agent-file-markdown.ts";

const identitySample = `# IDENTITY.md - Who Am I?

_Fill this in during your first conversation. Make it yours._

- **Name:**
  Molty
- **Creature:**
  AI familiar
- **Vibe:**
  Warm and direct
- **Emoji:**
  🦞
- **Avatar:**
  avatars/molty.png

## Related

- [Agent workspace](/concepts/agent-workspace)
`;

const userSample = `# USER.md - About Your Human

- **Name:** Alex
- **What to call them:** Alex
- **Pronouns:** they/them
- **Timezone:** America/Los_Angeles
- **Notes:**
  - Likes concise answers

## Context

Works on pharmacy tooling.

## Related

- [Agent workspace](/concepts/agent-workspace)
`;

const soulSample = `# SOUL.md - Who You Are

_You're not a chatbot. You're becoming someone._

## Core Truths

Be genuinely helpful.

## Boundaries

Private things stay private.

## Vibe

Concise when needed.

## Continuity

These files are your memory.

## Related

- [SOUL.md personality guide](/concepts/soul)
`;

describe("agent-file-markdown codec", () => {
  it("detects editable workspace config files", () => {
    expect(isEditableAgentConfigFile("IDENTITY.md")).toBe(true);
    expect(isEditableAgentConfigFile("README.md")).toBe(false);
  });

  it("parses IDENTITY bullet fields and preserves related epilogue", () => {
    const model = parseAgentFileMarkdown("IDENTITY.md", identitySample);
    expect(model.fields.map((field) => field.label)).toEqual([
      "Name",
      "Creature",
      "Vibe",
      "Emoji",
      "Avatar",
    ]);
    expect(model.fields[0]?.value).toBe("Molty");
    expect(model.sections).toEqual([]);
    expect(model.epilogue).toContain("Related");
    expect(model.preamble).toContain("# IDENTITY.md");
  });

  it("parses USER profile fields and context section", () => {
    const model = parseAgentFileMarkdown("USER.md", userSample);
    expect(model.fields.find((field) => field.label === "Name")?.value).toBe("Alex");
    expect(model.sections.find((section) => section.title === "Context")?.value).toBe(
      "Works on pharmacy tooling.",
    );
  });

  it("parses SOUL sections into textareas", () => {
    const model = parseAgentFileMarkdown("SOUL.md", soulSample);
    expect(model.fields).toEqual([]);
    expect(model.sections.map((section) => section.title)).toEqual([
      "Core Truths",
      "Boundaries",
      "Vibe",
      "Continuity",
    ]);
    expect(model.sections[0]?.value).toBe("Be genuinely helpful.");
  });

  it("round-trips IDENTITY edits through serialize", () => {
    const model = parseAgentFileMarkdown("IDENTITY.md", identitySample);
    const updated = applyAgentFileFormChange(model, {
      type: "field",
      id: "name",
      value: "Clawd",
    });
    const markdown = buildAgentFileMarkdownFromForm(updated);
    const reparsed = parseAgentFileMarkdown("IDENTITY.md", markdown);
    expect(reparsed.fields.find((field) => field.id === "name")?.value).toBe("Clawd");
    expect(markdown).toContain("- **Name:** Clawd");
    expect(markdown).toContain("## Related");
  });

  it("round-trips section edits for AGENTS.md headings", () => {
    const agentsSample = `# AGENTS.md - Your Workspace

Home base.

## First Run

Follow BOOTSTRAP.md once.

## Memory

Write things down.
`;
    const model = parseAgentFileMarkdown("AGENTS.md", agentsSample);
    const updated = applyAgentFileFormChange(model, {
      type: "section",
      id: "memory",
      value: "Capture what matters.",
    });
    const markdown = serializeAgentFileMarkdown(updated);
    expect(markdown).toContain("## Memory\n\nCapture what matters.");
    expect(
      parseAgentFileMarkdown("AGENTS.md", markdown).sections.find((s) => s.id === "memory")?.value,
    ).toBe("Capture what matters.");
  });
});
