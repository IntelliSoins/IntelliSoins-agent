/* @vitest-environment jsdom */

import { html, nothing, render } from "lit";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NAV_WIDTH_DEFAULT, NAV_WIDTH_MAX, NAV_WIDTH_MIN } from "../storage.ts";
import "./sidebar-resizer.ts";
import type { SidebarResizer } from "./sidebar-resizer.ts";

let container: HTMLDivElement;
const originalPointerEvent = globalThis.PointerEvent;

class TestPointerEvent extends MouseEvent {
  readonly pointerId: number;
  readonly pointerType: string;
  readonly isPrimary: boolean;

  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 1;
    this.pointerType = init.pointerType ?? "mouse";
    this.isPrimary = init.isPrimary ?? true;
  }
}

function nextFrame() {
  return new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve());
  });
}

async function renderResizer(navWidth = 260) {
  render(
    html`
      <sidebar-resizer
        .navWidth=${navWidth}
        .minWidth=${NAV_WIDTH_MIN}
        .maxWidth=${NAV_WIDTH_MAX}
        .defaultWidth=${NAV_WIDTH_DEFAULT}
        .label=${"Resize sidebar"}
      ></sidebar-resizer>
    `,
    container,
  );

  const resizer = container.querySelector<SidebarResizer>("sidebar-resizer");
  expect(resizer?.tagName.toLowerCase()).toBe("sidebar-resizer");
  if (!resizer) {
    throw new Error("expected sidebar resizer fixture");
  }

  await resizer.updateComplete;
  await nextFrame();
  return resizer;
}

function dispatchPointer(target: EventTarget, type: string, clientX: number) {
  target.dispatchEvent(
    new PointerEvent(type, {
      bubbles: true,
      button: 0,
      cancelable: true,
      clientX,
      pointerId: 7,
      pointerType: "touch",
    }),
  );
}

function expectLastResizeWidth(resized: ReturnType<typeof vi.fn>, navWidth: number) {
  const event = resized.mock.lastCall?.[0] as CustomEvent<{ navWidth: number }> | undefined;
  expect(event?.detail.navWidth).toBe(navWidth);
}

describe("sidebar-resizer", () => {
  beforeEach(() => {
    if (!globalThis.PointerEvent) {
      Object.defineProperty(globalThis, "PointerEvent", {
        configurable: true,
        value: TestPointerEvent as typeof PointerEvent,
      });
    }
    container = document.createElement("div");
    document.body.append(container);
  });

  afterEach(() => {
    render(nothing, container);
    container.remove();
    if (originalPointerEvent) {
      Object.defineProperty(globalThis, "PointerEvent", {
        configurable: true,
        value: originalPointerEvent,
      });
    } else {
      delete (globalThis as Partial<typeof globalThis>).PointerEvent;
    }
    vi.restoreAllMocks();
  });

  it("exposes separator semantics and current width on the host", async () => {
    const resizer = await renderResizer(280);

    expect(resizer.classList.contains("sidebar-resizer")).toBe(true);
    expect(resizer.getAttribute("role")).toBe("separator");
    expect(resizer.getAttribute("tabindex")).toBe("0");
    expect(resizer.getAttribute("aria-label")).toBe("Resize sidebar");
    expect(resizer.getAttribute("aria-orientation")).toBe("vertical");
    expect(resizer.getAttribute("aria-valuemin")).toBe(String(NAV_WIDTH_MIN));
    expect(resizer.getAttribute("aria-valuemax")).toBe(String(NAV_WIDTH_MAX));
    expect(resizer.getAttribute("aria-valuenow")).toBe("280");
  });

  it("resizes with keyboard arrows, Home, and End", async () => {
    const resizer = await renderResizer(260);
    const resized = vi.fn();
    resizer.addEventListener("resize", resized);

    const arrowLeft = new KeyboardEvent("keydown", {
      key: "ArrowLeft",
      bubbles: true,
      cancelable: true,
    });
    resizer.dispatchEvent(arrowLeft);
    expect(arrowLeft.defaultPrevented).toBe(true);
    expectLastResizeWidth(resized, 250);

    const arrowRight = new KeyboardEvent("keydown", {
      key: "ArrowRight",
      shiftKey: true,
      bubbles: true,
      cancelable: true,
    });
    resizer.dispatchEvent(arrowRight);
    expect(arrowRight.defaultPrevented).toBe(true);
    expectLastResizeWidth(resized, 280);

    resizer.dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true }));
    expectLastResizeWidth(resized, NAV_WIDTH_MIN);

    resizer.dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true }));
    expectLastResizeWidth(resized, NAV_WIDTH_MAX);
  });

  it("uses pointer events for dragging", async () => {
    const resizer = await renderResizer(260);
    const resized = vi.fn();
    const setPointerCapture = vi.fn();
    const releasePointerCapture = vi.fn();
    const hasPointerCapture = vi.fn(() => true);
    resizer.setPointerCapture = setPointerCapture;
    resizer.releasePointerCapture = releasePointerCapture;
    resizer.hasPointerCapture = hasPointerCapture;
    resizer.addEventListener("resize", resized);

    dispatchPointer(resizer, "pointerdown", 100);
    expect(document.activeElement).toBe(resizer);
    expect([...resizer.classList]).toContain("dragging");
    expect(setPointerCapture).toHaveBeenCalledWith(7);

    dispatchPointer(document, "pointermove", 150);
    expectLastResizeWidth(resized, 310);

    dispatchPointer(document, "pointerup", 150);
    expect(resizer.classList.contains("dragging")).toBe(false);
    expect(releasePointerCapture).toHaveBeenCalledWith(7);
  });

  it("resets to the default width on double-click", async () => {
    const resizer = await renderResizer(360);
    const resized = vi.fn();
    resizer.addEventListener("resize", resized);

    resizer.dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
    expectLastResizeWidth(resized, NAV_WIDTH_DEFAULT);
  });
});
