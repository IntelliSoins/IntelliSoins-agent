import { t } from "../i18n/index.js";

type MinimalTheme = {
  dim: (s: string) => string;
  bold: (s: string) => string;
  accentSoft: (s: string) => string;
};

const FALLBACK_PHRASES = [
  "flibbertigibbeting",
  "kerfuffling",
  "dillydallying",
  "twiddling thumbs",
  "noodling",
  "bamboozling",
  "moseying",
  "hobnobbing",
  "pondering",
  "conjuring",
];

/** Build waiting phrases from i18n, falling back to English defaults. */
export function getLocalizedWaitingPhrases(): string[] {
  const phrases: string[] = [];
  for (let i = 0; i < 10; i++) {
    const key = `tui.waiting.${i}`;
    const value = t(key);
    if (value !== key) {
      phrases.push(value);
    }
  }
  return phrases.length > 0 ? phrases : FALLBACK_PHRASES;
}

export const defaultWaitingPhrases = FALLBACK_PHRASES;

export function pickWaitingPhrase(tick: number, phrases = defaultWaitingPhrases) {
  const idx = Math.floor(tick / 10) % phrases.length;
  return phrases[idx] ?? phrases[0] ?? "waiting";
}

export function shimmerText(theme: MinimalTheme, text: string, tick: number) {
  const width = 6;
  const hi = (ch: string) => theme.bold(theme.accentSoft(ch));

  const pos = tick % (text.length + width);
  const start = Math.max(0, pos - width);
  const end = Math.min(text.length - 1, pos);

  let out = "";
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    out += i >= start && i <= end ? hi(ch) : theme.dim(ch);
  }
  return out;
}

export function buildWaitingStatusMessage(params: {
  theme: MinimalTheme;
  tick: number;
  elapsed: string;
  connectionStatus: string;
  phrases?: string[];
}) {
  const phrases = params.phrases ?? getLocalizedWaitingPhrases();
  const phrase = pickWaitingPhrase(params.tick, phrases);
  const cute = shimmerText(params.theme, `${phrase}…`, params.tick);
  return `${cute} • ${params.elapsed} | ${params.connectionStatus}`;
}
