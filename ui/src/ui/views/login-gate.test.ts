/* @vitest-environment jsdom */

import { render } from "lit";
import { beforeEach, describe, expect, it } from "vitest";
import { ConnectErrorDetailCodes } from "../../../../packages/gateway-protocol/src/connect-error-details.js";
import { i18n } from "../../i18n/index.ts";
import type { AppViewState } from "../app-view-state.ts";
import { renderLoginGate, resolveLoginFailureFeedback } from "./login-gate.ts";

function createState(overrides: Partial<AppViewState> = {}): AppViewState {
  return {
    basePath: "",
    connected: false,
    lastError: null,
    lastErrorCode: null,
    loginUsername: "",
    loginMfaCode: "",
    loginShowAdvanced: false,
    loginShowGatewayToken: false,
    loginShowGatewayPassword: false,
    password: "",
    settings: {
      gatewayUrl: "ws://127.0.0.1:18789",
      token: "",
      sessionKey: "main",
      lastActiveSessionKey: "main",
      theme: "claw",
      themeMode: "system",
      chatShowThinking: true,
      chatShowToolCalls: true,
      splitRatio: 0.6,
      navCollapsed: false,
      navWidth: 220,
      navGroupsCollapsed: {},
      borderRadius: 50,
      locale: "en",
    },
    applySettings: () => undefined,
    connect: () => undefined,
    ...overrides,
  } as unknown as AppViewState;
}

describe("resolveLoginFailureFeedback", () => {
  beforeEach(async () => {
    await i18n.setLocale("en");
  });

  it("explains missing user credentials", () => {
    const feedback = resolveLoginFailureFeedback({
      connected: false,
      lastError: "disconnected (4008): connect failed",
      lastErrorCode: ConnectErrorDetailCodes.AUTH_USER_REQUIRED,
      hasToken: false,
      hasPassword: false,
      hasUsername: false,
    });

    expect(feedback?.kind).toBe("auth-required");
    expect(feedback?.title).toBe("Authentification requise");
    expect(feedback?.steps[0]).toContain("nom d'utilisateur");
  });

  it("explains MFA requirement", () => {
    const feedback = resolveLoginFailureFeedback({
      connected: false,
      lastError: "mfa required",
      lastErrorCode: ConnectErrorDetailCodes.AUTH_USER_MFA_REQUIRED,
      hasToken: false,
      hasPassword: true,
      hasUsername: true,
    });
    expect(feedback?.kind).toBe("mfa-required");
    expect(feedback?.title).toBe("Code MFA requis");
  });

  it("explains rejected credentials", () => {
    const feedback = resolveLoginFailureFeedback({
      connected: false,
      lastError: "unauthorized",
      lastErrorCode: ConnectErrorDetailCodes.AUTH_USER_CREDENTIALS_INVALID,
      hasToken: false,
      hasPassword: true,
      hasUsername: true,
    });

    expect(feedback?.kind).toBe("auth-failed");
    expect(feedback?.summary).toContain("n'ont pas été acceptées");
  });
});

describe("renderLoginGate", () => {
  beforeEach(async () => {
    await i18n.setLocale("en");
  });

  it("renders pharmacist login fields and advanced settings", () => {
    const host = document.createElement("div");
    const state = createState();
    render(renderLoginGate(state), host);

    expect(host.textContent).toContain("Nom d'utilisateur");
    expect(host.textContent).toContain("Mot de passe");
    expect(host.textContent).toContain("Code MFA");
    expect(host.textContent).toContain("Paramètres avancés");
    expect(host.textContent).not.toContain("intellisoins gateway run");
  });
});
