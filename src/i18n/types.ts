/** Flat dot-notation key → translated string map. */
export type TranslationMap = Record<string, string>;

/** Supported locale codes. */
export type Locale = "en" | "fr";

export const SUPPORTED_LOCALES: readonly Locale[] = ["en", "fr"] as const;

export const DEFAULT_LOCALE: Locale = "en";

export function isSupportedLocale(value: unknown): value is Locale {
  return typeof value === "string" && (SUPPORTED_LOCALES as readonly string[]).includes(value);
}
