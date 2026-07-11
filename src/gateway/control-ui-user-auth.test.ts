// Control UI user-account auth tests.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runDummyPasswordVerify, verifyPassword } from "../security/password-hash.js";
import { resolveTotpCounterForCode } from "../security/totp.js";
import { createAuthRateLimiter } from "./auth-rate-limit.js";
import { authorizeControlUiUserAccountAuth } from "./control-ui-user-auth.js";
import {
  findControlUiUserByUsername,
  recordControlUiUserTotpSuccess,
  resolveControlUiUserTotpSecret,
} from "./control-ui-users.sqlite.js";

const mockUser = {
  userId: "u1",
  username: "pharma",
  passwordHash: "hash",
  totpSecretEncrypted: "enc",
  totpEnabled: true,
  totpLastCounter: null,
  createdAtMs: 1,
  updatedAtMs: 1,
};

vi.mock("../security/password-hash.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../security/password-hash.js")>();
  return {
    ...actual,
    verifyPassword: vi.fn(actual.verifyPassword),
    runDummyPasswordVerify: vi.fn(actual.runDummyPasswordVerify),
  };
});

vi.mock("./control-ui-users.sqlite.js", () => ({
  findControlUiUserByUsername: vi.fn((username: string) =>
    username === "missing" ? null : { ...mockUser, username },
  ),
  resolveControlUiUserTotpSecret: vi.fn(() => "JBSWY3DPEHPK3PXP"),
  recordControlUiUserTotpSuccess: vi.fn(),
}));

vi.mock("../security/totp.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../security/totp.js")>();
  return {
    ...actual,
    resolveTotpCounterForCode: vi.fn(actual.resolveTotpCounterForCode),
  };
});

describe("authorizeControlUiUserAccountAuth", () => {
  beforeEach(() => {
    vi.mocked(findControlUiUserByUsername).mockImplementation((username: string) =>
      username === "missing" ? null : { ...mockUser, username },
    );
    vi.mocked(verifyPassword).mockImplementation((_password, hash) => hash === "good-hash");
    vi.mocked(resolveControlUiUserTotpSecret).mockReturnValue("JBSWY3DPEHPK3PXP");
    vi.mocked(resolveTotpCounterForCode).mockImplementation((_secret, code) =>
      code === "123456" ? 42 : null,
    );
    vi.mocked(runDummyPasswordVerify).mockClear();
    vi.mocked(recordControlUiUserTotpSuccess).mockClear();
  });

  it("returns null when user credentials are absent", () => {
    expect(authorizeControlUiUserAccountAuth({ connectAuth: { token: "x" } })).toBeNull();
  });

  it("rejects unknown users and bad passwords with one generic reason", () => {
    expect(
      authorizeControlUiUserAccountAuth({
        connectAuth: { username: "pharma", password: "wrong" },
      })?.reason,
    ).toBe("user_credentials_invalid");
    expect(
      authorizeControlUiUserAccountAuth({
        connectAuth: { username: "missing", password: "SecurePass1" },
      })?.reason,
    ).toBe("user_credentials_invalid");
  });

  it("runs dummy scrypt for unknown users", () => {
    authorizeControlUiUserAccountAuth({
      connectAuth: { username: "missing", password: "SecurePass1" },
    });
    expect(runDummyPasswordVerify).toHaveBeenCalledWith("SecurePass1");
  });

  it("requires MFA enrollment before accepting credentials", () => {
    vi.mocked(findControlUiUserByUsername).mockReturnValueOnce({
      ...mockUser,
      passwordHash: "good-hash",
      totpEnabled: false,
    });
    expect(
      authorizeControlUiUserAccountAuth({
        connectAuth: { username: "pharma", password: "good-password" },
      })?.reason,
    ).toBe("user_mfa_required");
  });

  it("accepts valid credentials with MFA", () => {
    vi.mocked(findControlUiUserByUsername).mockReturnValueOnce({
      ...mockUser,
      passwordHash: "good-hash",
    });
    expect(
      authorizeControlUiUserAccountAuth({
        connectAuth: { username: "pharma", password: "good-password", mfaCode: "123456" },
      }),
    ).toEqual({ ok: true, method: "user-account", user: "pharma" });
    expect(recordControlUiUserTotpSuccess).toHaveBeenCalledWith("u1", 42, { env: undefined });
  });

  it("rejects invalid MFA codes", () => {
    vi.mocked(findControlUiUserByUsername).mockReturnValueOnce({
      ...mockUser,
      passwordHash: "good-hash",
    });
    expect(
      authorizeControlUiUserAccountAuth({
        connectAuth: { username: "pharma", password: "good-password", mfaCode: "000000" },
      })?.reason,
    ).toBe("user_mfa_invalid");
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
