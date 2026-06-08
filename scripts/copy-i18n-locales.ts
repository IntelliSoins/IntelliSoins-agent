#!/usr/bin/env tsx
/**
 * Copy i18n locale JSON files from src/i18n/locales to dist/i18n/locales.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");

const srcLocales = path.join(projectRoot, "src", "i18n", "locales");
const distLocales = path.join(projectRoot, "dist", "i18n", "locales");

function copyI18nLocales() {
  if (!fs.existsSync(srcLocales)) {
    console.warn("[copy-i18n-locales] Source directory not found:", srcLocales);
    return;
  }

  fs.mkdirSync(distLocales, { recursive: true });

  const files = fs.readdirSync(srcLocales).filter((f) => f.endsWith(".json"));
  let copiedCount = 0;

  for (const file of files) {
    fs.copyFileSync(path.join(srcLocales, file), path.join(distLocales, file));
    copiedCount += 1;
  }

  console.log(`[copy-i18n-locales] Copied ${copiedCount} locale files.`);
}

copyI18nLocales();
