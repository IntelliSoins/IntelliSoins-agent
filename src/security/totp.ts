// TOTP (RFC 6238) helpers for Control UI MFA enrollment and verification.
import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { safeEqualSecret } from "./secret-equal.js";

const BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
const DEFAULT_PERIOD_SECONDS = 30;
const DEFAULT_DIGITS = 6;
const DEFAULT_WINDOW_STEPS = 1;

function encodeBase32(buffer: Buffer): string {
  let bits = 0;
  let value = 0;
  let output = "";
  for (const byte of buffer) {
    value = (value << 8) | byte;
    bits += 8;
    while (bits >= 5) {
      output += BASE32_ALPHABET[(value >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  if (bits > 0) {
    output += BASE32_ALPHABET[(value << (5 - bits)) & 31];
  }
  return output;
}

function decodeBase32(input: string): Buffer | null {
  const normalized = input.trim().replace(/=+$/g, "").toUpperCase();
  if (!normalized || !/^[A-Z2-7]+$/.test(normalized)) {
    return null;
  }
  let bits = 0;
  let value = 0;
  const bytes: number[] = [];
  for (const char of normalized) {
    const index = BASE32_ALPHABET.indexOf(char);
    if (index < 0) {
      return null;
    }
    value = (value << 5) | index;
    bits += 5;
    if (bits >= 8) {
      bytes.push((value >>> (bits - 8)) & 0xff);
      bits -= 8;
    }
  }
  return Buffer.from(bytes);
}

function hotp(secret: Buffer, counter: bigint, digits: number): string {
  const counterBuffer = Buffer.alloc(8);
  counterBuffer.writeBigUInt64BE(counter);
  const digest = createHmac("sha1", secret).update(counterBuffer).digest();
  const offset = digest[digest.length - 1]! & 0x0f;
  const code =
    ((digest[offset]! & 0x7f) << 24) |
    ((digest[offset + 1]! & 0xff) << 16) |
    ((digest[offset + 2]! & 0xff) << 8) |
    (digest[offset + 3]! & 0xff);
  return String(code % 10 ** digits).padStart(digits, "0");
}

function totpAt(
  secret: Buffer,
  unixSeconds: number,
  periodSeconds: number,
  digits: number,
): string {
  const counter = BigInt(Math.floor(unixSeconds / periodSeconds));
  return hotp(secret, counter, digits);
}

/** Generate a new base32 TOTP secret suitable for authenticator apps. */
export function generateTotpSecret(): string {
  return encodeBase32(randomBytes(20));
}

/** Build an otpauth URI for QR enrollment. */
export function buildTotpOtpauthUri(params: {
  issuer: string;
  accountName: string;
  secret: string;
}): string {
  const issuer = encodeURIComponent(params.issuer);
  const account = encodeURIComponent(params.accountName);
  const secret = encodeURIComponent(params.secret);
  return `otpauth://totp/${issuer}:${account}?secret=${secret}&issuer=${issuer}&algorithm=SHA1&digits=${DEFAULT_DIGITS}&period=${DEFAULT_PERIOD_SECONDS}`;
}

/** Verify a 6-digit TOTP code against a base32 secret with a small clock-skew window. */
export function verifyTotpCode(
  secretBase32: string,
  code: string,
  options?: { unixSeconds?: number; windowSteps?: number },
): boolean {
  const normalizedCode = code.trim();
  if (!/^\d{6}$/.test(normalizedCode)) {
    return false;
  }
  const secret = decodeBase32(secretBase32);
  if (!secret) {
    return false;
  }
  const unixSeconds = options?.unixSeconds ?? Math.floor(Date.now() / 1000);
  const windowSteps = options?.windowSteps ?? DEFAULT_WINDOW_STEPS;
  const counterBase = Math.floor(unixSeconds / DEFAULT_PERIOD_SECONDS);
  for (let offset = -windowSteps; offset <= windowSteps; offset += 1) {
    const expected = totpAt(
      secret,
      (counterBase + offset) * DEFAULT_PERIOD_SECONDS,
      DEFAULT_PERIOD_SECONDS,
      DEFAULT_DIGITS,
    );
    if (safeEqualSecret(expected, normalizedCode)) {
      return true;
    }
  }
  return false;
}

/** Resolve the TOTP counter when a code is valid inside the configured clock-skew window. */
export function resolveTotpCounterForCode(
  secretBase32: string,
  code: string,
  options?: { unixSeconds?: number; windowSteps?: number },
): number | null {
  const normalizedCode = code.trim();
  if (!/^\d{6}$/.test(normalizedCode)) {
    return null;
  }
  const secret = decodeBase32(secretBase32);
  if (!secret) {
    return null;
  }
  const unixSeconds = options?.unixSeconds ?? Math.floor(Date.now() / 1000);
  const windowSteps = options?.windowSteps ?? DEFAULT_WINDOW_STEPS;
  const counterBase = Math.floor(unixSeconds / DEFAULT_PERIOD_SECONDS);
  for (let offset = -windowSteps; offset <= windowSteps; offset += 1) {
    const counter = counterBase + offset;
    const expected = totpAt(
      secret,
      counter * DEFAULT_PERIOD_SECONDS,
      DEFAULT_PERIOD_SECONDS,
      DEFAULT_DIGITS,
    );
    if (safeEqualSecret(expected, normalizedCode)) {
      return counter;
    }
  }
  return null;
}

/** Constant-time compare for TOTP codes (used in tests). */
export function equalTotpCode(left: string, right: string): boolean {
  const leftBuffer = Buffer.from(left.padStart(DEFAULT_DIGITS, "0"));
  const rightBuffer = Buffer.from(right.padStart(DEFAULT_DIGITS, "0"));
  if (leftBuffer.length !== rightBuffer.length) {
    return false;
  }
  return timingSafeEqual(leftBuffer, rightBuffer);
}
