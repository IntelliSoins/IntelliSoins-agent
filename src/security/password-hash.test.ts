// Password hashing tests for Control UI user accounts.
import { describe, expect, it } from "vitest";
import { hashPassword, verifyPassword } from "./password-hash.js";

describe("password-hash", () => {
  it("hashes and verifies a password", () => {
    const stored = hashPassword("PharmaSecure-42");
    expect(stored.startsWith("scrypt$")).toBe(true);
    expect(verifyPassword("PharmaSecure-42", stored)).toBe(true);
    expect(verifyPassword("wrong-password", stored)).toBe(false);
  });

  it("rejects malformed stored hashes", () => {
    expect(verifyPassword("secret", "bcrypt$abc")).toBe(false);
  });
});
