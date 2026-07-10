// Control UI tests cover agent workspace config form rendering.
import { render } from "lit";
import { describe, expect, it, vi } from "vitest";
import { renderAgentFileForm } from "./agent-file-form.ts";

const userSample = `# USER.md - About Your Human

- **Name:** Alex
- **What to call them:** Alex
- **Pronouns:** they/them
- **Timezone:** America/Los_Angeles
- **Notes:** Likes concise answers

## Context

Works on pharmacy tooling.
`;

describe("renderAgentFileForm", () => {
  it("renders structured fields instead of a default raw textarea", () => {
    const container = document.createElement("div");
    render(
      renderAgentFileForm({
        fileName: "USER.md",
        baseContent: userSample,
        draft: userSample,
        onDraftChange: () => undefined,
        onSave: () => undefined,
        onReset: () => undefined,
        onToggleRaw: () => undefined,
      }),
      container,
    );

    expect(container.querySelector(".agent-config-form")).toBeTruthy();
    expect(container.querySelectorAll(".agent-config-form__field input").length).toBeGreaterThan(0);
    expect(container.querySelector(".agent-config-form__section")).toBeTruthy();
    expect(container.querySelector(".agent-file-textarea")).toBeNull();
  });

  it("calls save and reset handlers from the form actions", () => {
    const container = document.createElement("div");
    const onSave = vi.fn();
    const onReset = vi.fn();
    const onToggleRaw = vi.fn();

    render(
      renderAgentFileForm({
        fileName: "USER.md",
        baseContent: userSample,
        draft: `${userSample}\nchanged`,
        onDraftChange: () => undefined,
        onSave,
        onReset,
        onToggleRaw,
      }),
      container,
    );

    const buttons = Array.from(
      container.querySelectorAll<HTMLButtonElement>(".agent-file-actions button"),
    );
    buttons.find((button) => button.textContent?.includes("Reset"))?.click();
    buttons.find((button) => button.textContent?.includes("Save"))?.click();
    buttons.find((button) => button.textContent?.includes("raw markdown"))?.click();

    expect(onReset).toHaveBeenCalledTimes(1);
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onToggleRaw).toHaveBeenCalledTimes(1);
  });
});
