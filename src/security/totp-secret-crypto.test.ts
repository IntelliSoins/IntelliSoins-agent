// TOTP secret encryption tests using persisted credentials key material.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import {
  decryptLegacyTotpSecret,
  decryptTotpSecret,
  encryptTotpSecret,
} from "./totp-secret-crypto.js";
import {
  deriveLegacyControlUiTotpEncryptionKey,
  resolveControlUiTotpEncryptionKey,
  resolveControlUiTotpEncryptionKeyPath,
} from "./totp-secret-key.js";

describe("totp-secret-crypto", () => {
  const env: NodeJS.ProcessEnv = {};
  let stateDir = "";

  afterEach(async () => {
    if (stateDir) {
      await fs.promises.rm(stateDir, { recursive: true, force: true });
      stateDir = "";
    }
  });

  it("encrypts and decrypts with a persisted random credentials key", async () => {
    stateDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), "openclaw-totp-key-"));
    env.OPENCLAW_STATE_DIR = stateDir;
    const secret = "JBSWY3DPEHPK3PXP";
    const payload = encryptTotpSecret(secret, env);
    expect(decryptTotpSecret(payload, env)).toBe(secret);
    const keyPath = resolveControlUiTotpEncryptionKeyPath(env);
    expect(fs.existsSync(keyPath)).toBe(true);
    const firstKey = resolveControlUiTotpEncryptionKey(env);
    const secondKey = resolveControlUiTotpEncryptionKey(env);
    expect(firstKey.equals(secondKey)).toBe(true);
    expect(firstKey.length).toBe(32);
  });

  it("migrates legacy path-derived payloads to the persisted key", async () => {
    stateDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), "openclaw-totp-legacy-"));
    env.OPENCLAW_STATE_DIR = stateDir;
    const secret = "JBSWY3DPEHPK3PXP";
    const legacyKey = deriveLegacyControlUiTotpEncryptionKey(env);
    const { createCipheriv, randomBytes } = await import("node:crypto");
    const iv = randomBytes(12);
    const cipher = createCipheriv("aes-256-gcm", legacyKey.subarray(0, 32), iv);
    const ciphertext = Buffer.concat([cipher.update(secret, "utf8"), cipher.final()]);
    const legacyPayload = [
      iv.toString("base64url"),
      cipher.getAuthTag().toString("base64url"),
      ciphertext.toString("base64url"),
    ].join(".");
    expect(decryptTotpSecret(legacyPayload, env)).toBeNull();
    expect(decryptLegacyTotpSecret(legacyPayload, env)).toBe(secret);
    const migrated = encryptTotpSecret(secret, env);
    expect(decryptTotpSecret(migrated, env)).toBe(secret);
  });
});
