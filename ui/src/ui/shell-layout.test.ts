/* @vitest-environment jsdom */

import { describe, expect, it, vi } from "vitest";
import { isDesktopShellLayout } from "./shell-layout.ts";
import { setViewportWidth } from "./test-helpers/app-mount.ts";

describe("shell-layout", () => {
  it("detects desktop shell layout from viewport width", () => {
    setViewportWidth(1280);
    expect(isDesktopShellLayout()).toBe(true);

    setViewportWidth(390);
    expect(isDesktopShellLayout()).toBe(false);
  });

  it("falls back to innerWidth when matchMedia is unavailable", () => {
    const originalMatchMedia = window.matchMedia;
    vi.stubGlobal("matchMedia", undefined);
    setViewportWidth(1280);
    expect(isDesktopShellLayout()).toBe(true);
    setViewportWidth(900);
    expect(isDesktopShellLayout()).toBe(false);
    vi.stubGlobal("matchMedia", originalMatchMedia);
  });
});
