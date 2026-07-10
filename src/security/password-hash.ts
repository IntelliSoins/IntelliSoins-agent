// Password hashing for stored user credentials using scrypt.
import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto";

const SCRYPT_PREFIX = "scrypt";
const SCRYPT_SALT_BYTES = 16;
const SCRYPT_KEY_BYTES = 64;
const SCRYPT_N = 16384;
const SCRYPT_R = 8;
const SCRYPT_P = 1;

function encodeBase64Url(buffer: Buffer): string {
  return buffer.toString("base64url");
}

function decodeBase64Url(value: string): Buffer {
  return Buffer.from(value, "base64url");
}

// Fixed dummy hash so unknown-user auth checks always run scrypt with stable timing.
const DUMMY_PASSWORD_HASH = (() => {
  const salt = Buffer.alloc(SCRYPT_SALT_BYTES, 0);
  const derived = scryptSync("__openclaw_dummy_user_auth__", salt, SCRYPT_KEY_BYTES, {
    N: SCRYPT_N,
    r: SCRYPT_R,
    p: SCRYPT_P,
  });
  return `${SCRYPT_PREFIX}$${encodeBase64Url(salt)}$${encodeBase64Url(derived)}`;
})();

/** Hash a plaintext password for storage; never persist the input password. */
export function hashPassword(password: string): string {
  const salt = randomBytes(SCRYPT_SALT_BYTES);
  const derived = scryptSync(password, salt, SCRYPT_KEY_BYTES, {
    N: SCRYPT_N,
    r: SCRYPT_R,
    p: SCRYPT_P,
  });
  return `${SCRYPT_PREFIX}$${encodeBase64Url(salt)}$${encodeBase64Url(derived)}`;
}

/** Verify a plaintext password against a stored scrypt hash. */
export function verifyPassword(password: string, storedHash: string): boolean {
  const parts = storedHash.split("$");
  if (parts.length !== 3 || parts[0] !== SCRYPT_PREFIX) {
    return false;
  }
  const salt = decodeBase64Url(parts[1] ?? "");
  const expected = decodeBase64Url(parts[2] ?? "");
  if (salt.length === 0 || expected.length === 0) {
    return false;
  }
  const actual = scryptSync(password, salt, expected.length, {
    N: SCRYPT_N,
    r: SCRYPT_R,
    p: SCRYPT_P,
  });
  if (actual.length !== expected.length) {
    return false;
  }
  return timingSafeEqual(actual, expected);
}

/** Run a scrypt verify against a fixed dummy hash to normalize unknown-user timing. */
export function runDummyPasswordVerify(password: string): void {
  verifyPassword(password, DUMMY_PASSWORD_HASH);
}
