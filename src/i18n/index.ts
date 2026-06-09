import { loadConfig } from "../config/config.js";
import { detectLocaleFromEnv, loadTranslations } from "./loader.js";
import type { Locale, TranslationMap } from "./types.js";
import { DEFAULT_LOCALE, isSupportedLocale } from "./types.js";

export type { Locale, TranslationMap } from "./types.js";
export { DEFAULT_LOCALE, SUPPORTED_LOCALES, isSupportedLocale } from "./types.js";
export { detectLocaleFromEnv } from "./loader.js";

let currentLocale: Locale = DEFAULT_LOCALE;
let translations: TranslationMap = {};
let initialized = false;

/**
 * Initialize the i18n system.
 *
 * Resolution order for locale:
 * 1. Explicit `locale` parameter
 * 2. `cli.locale` in openclaw.json
 * 3. OPENCLAW_LOCALE env var
 * 4. LANG / LC_ALL / LC_MESSAGES env vars
 * 5. Default: "en"
 */
export function initI18n(options?: { locale?: string; customTranslationsPath?: string }): void {
  // Resolve locale
  let locale: Locale;

  if (options?.locale && isSupportedLocale(options.locale)) {
    locale = options.locale;
  } else {
    // Try config
    try {
      const config = loadConfig();
      const configLocale = (config.cli as Record<string, unknown> | undefined)?.locale;
      if (typeof configLocale === "string" && isSupportedLocale(configLocale)) {
        locale = configLocale;
      } else {
        locale = detectLocaleFromEnv();
      }
    } catch {
      locale = detectLocaleFromEnv();
    }
  }

  currentLocale = locale;
  translations = loadTranslations(locale, options?.customTranslationsPath);
  initialized = true;
}

/**
 * Translate a key with optional interpolation variables.
 *
 * Usage:
 *   t("cli.banner.title")                    → "OpenClaw"
 *   t("cli.login.success", { name: "John" }) → "Linked! Welcome, John."
 *
 * Falls back to the key itself if no translation is found.
 */
export function t(key: string, vars?: Record<string, string>): string {
  if (!initialized) {
    initI18n();
  }

  let value = translations[key];
  if (value === undefined) {
    // Return the key as-is (makes missing translations visible).
    return key;
  }

  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      value = value.replaceAll(`{${k}}`, v);
    }
  }

  return value;
}

/** Get the current active locale. */
export function getLocale(): Locale {
  if (!initialized) {
    initI18n();
  }
  return currentLocale;
}

/** Reset i18n state (mainly for testing). */
export function resetI18n(): void {
  currentLocale = DEFAULT_LOCALE;
  translations = {};
  initialized = false;
}
