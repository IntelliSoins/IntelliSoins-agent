// Gateway users-mode auth tests for Control UI token bypass and user-account policy.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { authorizeHttpGatewayConnect, authorizeWsControlUiGatewayConnect } from "./auth.js";

vi.mock("./control-ui-user-auth.js", () => ({
  authorizeControlUiUserAccountAuth: vi.fn((params: { connectAuth?: { username?: string } }) => {
    if (params.connectAuth?.username) {
      return { ok: true, method: "user-account", user: params.connectAuth.username };
    }
    return null;
  }),
  hasExplicitUserAccountAuth: vi.fn((connectAuth?: { username?: string; password?: string }) =>
    Boolean(connectAuth?.username && connectAuth?.password),
  ),
}));

describe("gateway users auth mode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("rejects shared gateway tokens for Control UI websocket connects", async () => {
    const result = await authorizeWsControlUiGatewayConnect({
      auth: { mode: "users", token: "shared-token", allowTailscale: false },
      connectAuth: { token: "shared-token" },
    });
    expect(result).toEqual({ ok: false, reason: "user_auth_required" });
  });

  it("still accepts shared gateway tokens on the HTTP auth surface", async () => {
    const result = await authorizeHttpGatewayConnect({
      auth: { mode: "users", token: "shared-token", allowTailscale: false },
      connectAuth: { token: "shared-token" },
    });
    expect(result.ok).toBe(true);
    expect(result.method).toBe("token");
  });

  it("accepts user credentials on Control UI websocket connects", async () => {
    const result = await authorizeWsControlUiGatewayConnect({
      auth: { mode: "users", token: "shared-token", allowTailscale: false },
      connectAuth: { username: "pharma", password: "secret", mfaCode: "123456" },
    });
    expect(result).toEqual({ ok: true, method: "user-account", user: "pharma" });
  });
});
