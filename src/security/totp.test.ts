import { createHmac } from "node:crypto";
import { describe, expect, it } from "vitest";
import { generateTotpSecret, verifyTotpCode } from "./totp.js";

function currentTotpCode(secret: string): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const decode = (input: string) => {
    let bits = 0;
    let value = 0;
    const bytes: number[] = [];
    for (const char of input.toUpperCase()) {
      value = (value << 5) | alphabet.indexOf(char);
      bits += 5;
      if (bits >= 8) {
        bytes.push((value >>> (bits - 8)) & 0xff);
        bits -= 8;
      }
    }
    return Buffer.from(bytes);
  };
  const unixSeconds = Math.floor(Date.now() / 1000);
  const counter = Math.floor(unixSeconds / 30);
  const secretBuf = decode(secret);
  const counterBuffer = Buffer.alloc(8);
  counterBuffer.writeBigUInt64BE(BigInt(counter));
  const digest = createHmac("sha1", secretBuf).update(counterBuffer).digest();
  const offset = digest[digest.length - 1]! & 0x0f;
  const codeNum =
    ((digest[offset]! & 0x7f) << 24) |
    ((digest[offset + 1]! & 0xff) << 16) |
    ((digest[offset + 2]! & 0xff) << 8) |
    (digest[offset + 3]! & 0xff);
  return String(codeNum % 1_000_000).padStart(6, "0");
}

describe("totp", () => {
  it("accepts a freshly generated code", () => {
    const secret = generateTotpSecret();
    const code = currentTotpCode(secret);
    expect(verifyTotpCode(secret, code)).toBe(true);
    expect(verifyTotpCode(secret, "000000")).toBe(false);
  });
});
