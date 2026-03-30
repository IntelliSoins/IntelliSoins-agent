import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Locale, TranslationMap } from "./types.js";
import { DEFAULT_LOCALE, isSupportedLocale } from "./types.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Resolve the built-in locale JSON path. */
function builtinLocalePath(locale: Locale): string {
  return path.join(__dirname, "locales", `${locale}.json`);
}

/** Load a translation map from a JSON file. Returns empty map on failure. */
function loadJsonMap(filePath: string): TranslationMap {
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as TranslationMap;
    }
  } catch {
    // Silently fall back to empty map.
  }
  return {};
}

/**
 * Load translations for the given locale with English fallback.
 *
 * Resolution order:
 * 1. Custom translations file (if provided via config)
 * 2. Built-in locale file (`src/i18n/locales/<locale>.json`)
 * 3. Built-in English fallback
 */
export function loadTranslations(locale: Locale, customPath?: string): TranslationMap {
  const en = locale === DEFAULT_LOCALE ? {} : loadJsonMap(builtinLocalePath(DEFAULT_LOCALE));
  const target = loadJsonMap(builtinLocalePath(locale));
  const custom = customPath ? loadJsonMap(customPath) : {};

  // English base → locale override → custom override
  return { ...en, ...target, ...custom };
}

/**
 * Detect locale from environment variables.
 * Checks OPENCLAW_LOCALE, LANG, LC_ALL, LC_MESSAGES in order.
 */
export function detectLocaleFromEnv(): Locale {
  const candidates = [
    process.env.OPENCLAW_LOCALE,
    process.env.LANG,
    process.env.LC_ALL,
    process.env.LC_MESSAGES,
  ];

  for (const raw of candidates) {
    if (!raw) {
      continue;
    }
    // Extract language code: "fr_CA.UTF-8" → "fr", "en_US" → "en"
    const code = raw.split(/[_.@-]/)[0]?.toLowerCase();
    if (code && isSupportedLocale(code)) {
      return code;
    }
  }

  return DEFAULT_LOCALE;
}
