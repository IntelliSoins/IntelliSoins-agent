// Control UI user-account auth tests.
import { describe, expect, it, vi } from "vitest";
import { createAuthRateLimiter } from "./auth-rate-limit.js";
import { authorizeControlUiUserAccountAuth } from "./control-ui-user-auth.js";

vi.mock("./control-ui-users.sqlite.js", () => ({
  findControlUiUserByUsername: vi.fn((username: string) =>
    username === "missing" ? null : { userId: "u1", username, totpEnabled: false },
  ),
  verifyControlUiUserPassword: vi.fn((username: string, password: string) =>
    username === "pharma" && password === "SecurePass1"
      ? {
          userId: "u1",
          username: "pharma",
          passwordHash: "hash",
          totpSecretEncrypted: null,
          totpEnabled: false,
          createdAtMs: 1,
          updatedAtMs: 1,
        }
      : null,
  ),
  resolveControlUiUserTotpSecret: vi.fn(() => "JBSWY3DPEHPK3PXP"),
}));

describe("authorizeControlUiUserAccountAuth", () => {
  it("returns null when user credentials are absent", () => {
    expect(authorizeControlUiUserAccountAuth({ connectAuth: { token: "x" } })).toBeNull();
  });

  it("rejects unknown users and bad passwords", () => {
    expect(
      authorizeControlUiUserAccountAuth({
        connectAuth: { username: "pharma", password: "wrong" },
      })?.reason,
    ).toBe("user_password_mismatch");
    expect(
      authorizeControlUiUserAccountAuth({
        connectAuth: { username: "missing", password: "SecurePass1" },
      })?.reason,
    ).toBe("user_not_found");
  });

  it("accepts valid credentials without MFA", () => {
    expect(
      authorizeControlUiUserAccountAuth({
        connectAuth: { username: "pharma", password: "SecurePass1" },
      }),
    ).toEqual({ ok: true, method: "user-account", user: "pharma" });
  });

  it("records rate-limit failures", () => {
    const limiter = createAuthRateLimiter({ maxAttempts: 1, windowMs: 60_000, lockoutMs: 60_000 });
    authorizeControlUiUserAccountAuth({
      connectAuth: { username: "pharma", password: "wrong" },
      limiter,
      ip: "203.0.113.10",
    });
    const blocked = limiter.check("203.0.113.10", "user-account");
    expect(blocked.allowed).toBe(false);
  });
});
