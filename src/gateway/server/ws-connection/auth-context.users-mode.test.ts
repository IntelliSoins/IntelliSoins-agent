// WebSocket auth-context tests for user-account device pairing policy.
import { describe, expect, it, vi } from "vitest";
import type { AuthRateLimiter } from "../../auth-rate-limit.js";
import type { ResolvedGatewayAuth } from "../../auth.js";
import { resolveConnectAuthState } from "./auth-context.js";

vi.mock("../../auth.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../auth.js")>();
  return {
    ...actual,
    authorizeWsControlUiGatewayConnect: vi.fn(async () => ({
      ok: true,
      method: "user-account",
      user: "pharma",
    })),
    authorizeHttpGatewayConnect: vi.fn(async () => ({
      ok: true,
      method: "user-account",
      user: "pharma",
    })),
  };
});

function createLimiter(): AuthRateLimiter {
  return {
    check: vi.fn(() => ({ allowed: true, remaining: 10, retryAfterMs: 0 })),
    reset: vi.fn(),
    recordFailure: vi.fn(),
    size: vi.fn(() => 0),
    prune: vi.fn(),
    dispose: vi.fn(),
  };
}

describe("resolveConnectAuthState user-account pairing", () => {
  it("does not treat user-account auth as sharedAuthOk", async () => {
    const state = await resolveConnectAuthState({
      resolvedAuth: {
        mode: "users",
        allowTailscale: false,
      } satisfies ResolvedGatewayAuth,
      connectAuth: {
        username: "pharma",
        password: "secret",
        mfaCode: "123456",
      },
      hasDeviceIdentity: false,
      req: {
        headers: { origin: "https://control-ui.test" },
        socket: { remoteAddress: "203.0.113.10" },
      } as never,
      trustedProxies: [],
      allowRealIpFallback: false,
      rateLimiter: createLimiter(),
      clientIp: "203.0.113.10",
    });

    expect(state.authOk).toBe(true);
    expect(state.authMethod).toBe("user-account");
    expect(state.sharedAuthOk).toBe(false);
  });
});
