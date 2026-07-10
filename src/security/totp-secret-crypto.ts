// Encrypt/decrypt stored TOTP secrets at rest for Control UI user accounts.
import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";
import { resolveOpenClawStateSqliteDir } from "../state/openclaw-state-db.paths.js";

const ALGORITHM = "aes-256-gcm";
const IV_BYTES = 12;
const KEY_BYTES = 32;

function deriveTotpEncryptionKey(env: NodeJS.ProcessEnv = process.env): Buffer {
  const stateDir = resolveOpenClawStateSqliteDir(env);
  return createHash("sha256").update(`openclaw-control-ui-totp:${stateDir}`).digest();
}

function encodePayload(iv: Buffer, tag: Buffer, ciphertext: Buffer): string {
  return [
    iv.toString("base64url"),
    tag.toString("base64url"),
    ciphertext.toString("base64url"),
  ].join(".");
}

function decodePayload(payload: string): { iv: Buffer; tag: Buffer; ciphertext: Buffer } | null {
  const parts = payload.split(".");
  if (parts.length !== 3) {
    return null;
  }
  try {
    return {
      iv: Buffer.from(parts[0] ?? "", "base64url"),
      tag: Buffer.from(parts[1] ?? "", "base64url"),
      ciphertext: Buffer.from(parts[2] ?? "", "base64url"),
    };
  } catch {
    return null;
  }
}

/** Encrypt a base32 TOTP secret for SQLite storage. */
export function encryptTotpSecret(secret: string, env?: NodeJS.ProcessEnv): string {
  const key = deriveTotpEncryptionKey(env);
  const iv = randomBytes(IV_BYTES);
  const cipher = createCipheriv(ALGORITHM, key.subarray(0, KEY_BYTES), iv);
  const ciphertext = Buffer.concat([cipher.update(secret, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return encodePayload(iv, tag, ciphertext);
}

/** Decrypt a stored TOTP secret payload. */
export function decryptTotpSecret(payload: string, env?: NodeJS.ProcessEnv): string | null {
  const decoded = decodePayload(payload);
  if (!decoded || decoded.iv.length !== IV_BYTES) {
    return null;
  }
  try {
    const key = deriveTotpEncryptionKey(env);
    const decipher = createDecipheriv(ALGORITHM, key.subarray(0, KEY_BYTES), decoded.iv);
    decipher.setAuthTag(decoded.tag);
    const plaintext = Buffer.concat([decipher.update(decoded.ciphertext), decipher.final()]);
    return plaintext.toString("utf8");
  } catch {
    return null;
  }
}
