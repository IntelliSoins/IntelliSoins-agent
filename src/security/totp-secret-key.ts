// Resolve or create the Control UI TOTP encryption key stored under credentials/.
import { createHash, randomBytes } from "node:crypto";
import path from "node:path";
import { resolveOAuthDir } from "../config/paths.js";
import { privateFileStoreSync } from "../infra/private-file-store.js";
import { resolveOpenClawStateSqliteDir } from "../state/openclaw-state-db.paths.js";

const KEY_FILENAME = "control-ui-totp-key";
const KEY_BYTES = 32;

/** Return the persisted random 32-byte TOTP encryption key, creating it when missing. */
export function resolveControlUiTotpEncryptionKey(env: NodeJS.ProcessEnv = process.env): Buffer {
  const credentialsDir = resolveOAuthDir(env);
  const store = privateFileStoreSync(credentialsDir);
  const existing = store.readTextIfExists(KEY_FILENAME)?.trim();
  if (existing) {
    const key = Buffer.from(existing, "base64url");
    if (key.length === KEY_BYTES) {
      return key;
    }
  }
  const key = randomBytes(KEY_BYTES);
  store.writeText(KEY_FILENAME, key.toString("base64url"));
  return key;
}

/** Legacy path-derived key kept only for decrypting and re-encrypting older payloads. */
export function deriveLegacyControlUiTotpEncryptionKey(
  env: NodeJS.ProcessEnv = process.env,
): Buffer {
  const stateDir = resolveOpenClawStateSqliteDir(env);
  return createHash("sha256").update(`openclaw-control-ui-totp:${stateDir}`).digest();
}

/** Absolute path to the persisted TOTP encryption key file (tests/doctor diagnostics). */
export function resolveControlUiTotpEncryptionKeyPath(
  env: NodeJS.ProcessEnv = process.env,
): string {
  return path.join(resolveOAuthDir(env), KEY_FILENAME);
}
