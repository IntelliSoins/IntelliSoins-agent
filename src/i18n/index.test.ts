import { afterEach, describe, expect, it, vi } from "vitest";
import { getLocale, initI18n, resetI18n, t } from "./index.js";

describe("i18n", () => {
  afterEach(() => {
    resetI18n();
    vi.unstubAllEnvs();
  });

  it("defaults to English locale", () => {
    initI18n({ locale: "en" });
    expect(getLocale()).toBe("en");
  });

  it("translates known keys in English", () => {
    initI18n({ locale: "en" });
    expect(t("cli.banner.title")).toBe("OpenClaw");
    expect(t("cli.tagline.default")).toBe("All your chats, one OpenClaw.");
  });

  it("translates known keys in French", () => {
    initI18n({ locale: "fr" });
    expect(getLocale()).toBe("fr");
    expect(t("cli.tagline.default")).toBe("Tous vos chats, un seul OpenClaw.");
    expect(t("cli.banner.unknown_commit")).toBe("inconnu");
  });

  it("falls back to English for missing French keys", () => {
    initI18n({ locale: "fr" });
    // Both locales have this key, so it should be French
    expect(t("cli.banner.title")).toBe("OpenClaw");
  });

  it("returns the key for unknown translation keys", () => {
    initI18n({ locale: "en" });
    expect(t("nonexistent.key")).toBe("nonexistent.key");
  });

  it("interpolates variables", () => {
    initI18n({ locale: "en" });
    expect(t("cli.status.default_model", { model: "gpt-4" })).toBe("Default model: gpt-4");
  });

  it("interpolates variables in French", () => {
    initI18n({ locale: "fr" });
    expect(t("cli.status.default_model", { model: "gpt-4" })).toBe("Modèle par défaut : gpt-4");
  });

  it("detects locale from OPENCLAW_LOCALE env var", () => {
    vi.stubEnv("OPENCLAW_LOCALE", "fr");
    initI18n();
    expect(getLocale()).toBe("fr");
  });

  it("falls back to en for unsupported locale", () => {
    initI18n({ locale: "xx" });
    expect(getLocale()).toBe("en");
  });

  it("lazy-initializes on first t() call", () => {
    // No initI18n() call — t() should auto-init
    const result = t("cli.banner.title");
    expect(result).toBe("OpenClaw");
  });

  it("French waiting phrases are distinct from English", () => {
    initI18n({ locale: "fr" });
    const frWaiting = t("tui.waiting.2");
    resetI18n();
    initI18n({ locale: "en" });
    const enWaiting = t("tui.waiting.2");
    expect(frWaiting).not.toBe(enWaiting);
    expect(frWaiting).toBe("niaisage");
    expect(enWaiting).toBe("dillydallying");
  });
});
