// Control UI view renders login gate screen content.
import { html } from "lit";
import { ConnectErrorDetailCodes } from "../../../../packages/gateway-protocol/src/connect-error-details.js";
import { t } from "../../i18n/index.ts";
import type { AppViewState } from "../app-view-state.ts";
import { buildExternalLinkRel, EXTERNAL_LINK_TARGET } from "../external-link.ts";
import { icons } from "../icons.ts";
import { normalizeBasePath } from "../navigation.ts";
import { normalizeLowercaseStringOrEmpty } from "../string-coerce.ts";
import { agentLogoUrl } from "./agents-utils.ts";
import {
  resolveAuthHintKind,
  resolvePairingHint,
  shouldShowInsecureContextHint,
} from "./overview-hints.ts";

type LoginFailureKind =
  | "auth-required"
  | "auth-failed"
  | "auth-rate-limited"
  | "mfa-required"
  | "mfa-invalid"
  | "pairing-required"
  | "insecure-context"
  | "origin-not-allowed"
  | "protocol-mismatch"
  | "network";

export type LoginFailureFeedback = {
  kind: LoginFailureKind;
  title: string;
  summary: string;
  steps: string[];
  docsHref: string;
  docsLabel: string;
  rawError: string;
};

type LoginFailureFeedbackParams = {
  connected: boolean;
  lastError: string | null;
  lastErrorCode?: string | null;
  hasToken: boolean;
  hasPassword: boolean;
  hasUsername: boolean;
};

function resolveDocsLabel(href: string): string {
  if (href.includes("insecure-http")) {
    return t("login.failure.docsInsecure");
  }
  if (href.includes("device-pairing")) {
    return t("login.failure.docsPairing");
  }
  return t("login.failure.docsAuth");
}

function redactLoginFailureError(value: string): string {
  return value
    .replace(
      /([?#&])(?:access_token|auth|deviceToken|password|refresh_token|token|mfaCode|username)=([^&#\s]+)/gi,
      "$1[redacted-credential]",
    )
    .replace(/\bBearer\s+([A-Za-z0-9._~+/-]+=*)/gi, "Bearer [redacted]")
    .replace(
      /(["']?(?:access|accessToken|deviceToken|password|refresh|refreshToken|token|username|mfaCode)["']?\s*[:=]\s*)["']?[^"',\s}]+/gi,
      "$1[redacted]",
    );
}

function buildFeedback(params: {
  kind: LoginFailureKind;
  rawError: string;
  docsHref?: string;
  titleKey: string;
  summaryKey: string;
  stepKeys: string[];
  stepParams?: Record<string, string>;
}): LoginFailureFeedback {
  const docsHref = params.docsHref ?? "https://docs.openclaw.ai/web/control-ui-users";
  return {
    kind: params.kind,
    title: t(params.titleKey, params.stepParams),
    summary: t(params.summaryKey, params.stepParams),
    steps: params.stepKeys.map((key) => t(key, params.stepParams)),
    docsHref,
    docsLabel: resolveDocsLabel(docsHref),
    rawError: redactLoginFailureError(params.rawError),
  };
}

export function resolveLoginFailureFeedback(
  params: LoginFailureFeedbackParams,
): LoginFailureFeedback | null {
  if (params.connected || !params.lastError) {
    return null;
  }

  const rawError = params.lastError;
  const lastErrorCode = params.lastErrorCode ?? null;
  const lower = normalizeLowercaseStringOrEmpty(rawError);

  const pairing = resolvePairingHint(false, rawError, lastErrorCode);
  if (pairing) {
    return buildFeedback({
      kind: "pairing-required",
      rawError,
      docsHref: "https://docs.openclaw.ai/web/control-ui#device-pairing-first-connection",
      titleKey:
        pairing.kind === "scope-upgrade-pending"
          ? "login.failure.pairing.scopeTitle"
          : pairing.kind === "role-upgrade-pending"
            ? "login.failure.pairing.roleTitle"
            : pairing.kind === "metadata-upgrade-pending"
              ? "login.failure.pairing.metadataTitle"
              : "login.failure.pairing.title",
      summaryKey:
        pairing.kind === "pairing-required"
          ? "login.failure.pairing.summary"
          : "login.failure.pairing.upgradeSummary",
      stepKeys: [
        "login.failure.pairing.stepList",
        pairing.requestId
          ? "login.failure.pairing.stepApproveId"
          : "login.failure.pairing.stepApprove",
        "login.failure.pairing.stepReconnect",
      ],
      stepParams: { requestId: pairing.requestId ?? "" },
    });
  }

  if (
    lastErrorCode === ConnectErrorDetailCodes.AUTH_RATE_LIMITED ||
    lower.includes("too many failed authentication attempts") ||
    lower.includes("rate limit")
  ) {
    return buildFeedback({
      kind: "auth-rate-limited",
      rawError,
      titleKey: "login.failure.rateLimited.title",
      summaryKey: "login.failure.rateLimited.summary",
      stepKeys: [
        "login.failure.rateLimited.stepStop",
        "login.failure.rateLimited.stepWait",
        "login.failure.rateLimited.stepCheckClients",
      ],
    });
  }

  if (lastErrorCode === ConnectErrorDetailCodes.AUTH_USER_MFA_REQUIRED) {
    return buildFeedback({
      kind: "mfa-required",
      rawError,
      titleKey: "login.failure.mfaRequired.title",
      summaryKey: "login.failure.mfaRequired.summary",
      stepKeys: ["login.failure.mfaRequired.stepCode", "login.failure.mfaRequired.stepRetry"],
    });
  }

  if (lastErrorCode === ConnectErrorDetailCodes.AUTH_USER_MFA_INVALID) {
    return buildFeedback({
      kind: "mfa-invalid",
      rawError,
      titleKey: "login.failure.mfaInvalid.title",
      summaryKey: "login.failure.mfaInvalid.summary",
      stepKeys: ["login.failure.mfaInvalid.stepClock", "login.failure.mfaInvalid.stepRetry"],
    });
  }

  if (shouldShowInsecureContextHint(false, rawError, lastErrorCode)) {
    return buildFeedback({
      kind: "insecure-context",
      rawError,
      docsHref: "https://docs.openclaw.ai/web/control-ui#insecure-http",
      titleKey: "login.failure.insecure.title",
      summaryKey: "login.failure.insecure.summary",
      stepKeys: [
        "login.failure.insecure.stepHttps",
        "login.failure.insecure.stepLocalCompat",
        "login.failure.insecure.stepAvoidDisable",
      ],
    });
  }

  if (
    lastErrorCode === ConnectErrorDetailCodes.CONTROL_UI_ORIGIN_NOT_ALLOWED ||
    lower.includes("origin not allowed")
  ) {
    return buildFeedback({
      kind: "origin-not-allowed",
      rawError,
      docsHref:
        "https://docs.openclaw.ai/web/control-ui#debuggingtesting-dev-server--remote-gateway",
      titleKey: "login.failure.origin.title",
      summaryKey: "login.failure.origin.summary",
      stepKeys: [
        "login.failure.origin.stepAllowedOrigins",
        "login.failure.origin.stepFullOrigin",
        "login.failure.origin.stepRestart",
      ],
    });
  }

  if (lower.includes("protocol mismatch")) {
    return buildFeedback({
      kind: "protocol-mismatch",
      rawError,
      docsHref:
        "https://docs.openclaw.ai/web/control-ui#debuggingtesting-dev-server--remote-gateway",
      titleKey: "login.failure.protocol.title",
      summaryKey: "login.failure.protocol.summary",
      stepKeys: [
        "login.failure.protocol.stepDashboard",
        "login.failure.protocol.stepDevUi",
        "login.failure.protocol.stepRestart",
      ],
    });
  }

  const authHintKind = resolveAuthHintKind({
    connected: false,
    lastError: rawError,
    lastErrorCode,
    hasToken: params.hasToken,
    hasPassword: params.hasPassword,
    hasUsername: params.hasUsername,
  });
  if (authHintKind === "required") {
    return buildFeedback({
      kind: "auth-required",
      rawError,
      titleKey: "login.failure.authRequired.title",
      summaryKey: "login.failure.authRequired.summary",
      stepKeys: [
        "login.failure.authRequired.stepCredentials",
        "login.failure.authRequired.stepMfa",
        "login.failure.authRequired.stepConnect",
      ],
    });
  }
  if (authHintKind === "failed") {
    return buildFeedback({
      kind: "auth-failed",
      rawError,
      titleKey: "login.failure.authFailed.title",
      summaryKey: "login.failure.authFailed.summary",
      stepKeys: [
        "login.failure.authFailed.stepCheck",
        "login.failure.authFailed.stepMfa",
        "login.failure.authFailed.stepAdmin",
      ],
    });
  }

  return buildFeedback({
    kind: "network",
    rawError,
    titleKey: "login.failure.network.title",
    summaryKey: "login.failure.network.summary",
    stepKeys: [
      "login.failure.network.stepGateway",
      "login.failure.network.stepUrl",
      "login.failure.network.stepDashboard",
    ],
  });
}

function renderLoginFailure(feedback: LoginFailureFeedback) {
  return html`
    <div
      class="callout danger login-gate__failure"
      role="alert"
      aria-live="polite"
      data-kind=${feedback.kind}
    >
      <div class="login-gate__failure-title">${feedback.title}</div>
      <div class="login-gate__failure-summary">${feedback.summary}</div>
      <ol class="login-gate__failure-steps">
        ${feedback.steps.map((step) => html`<li>${step}</li>`)}
      </ol>
      <details class="login-gate__failure-detail">
        <summary>${t("login.failure.rawError")}</summary>
        <div class="login-gate__failure-raw mono">${feedback.rawError}</div>
      </details>
      <a
        class="session-link login-gate__failure-docs"
        href=${feedback.docsHref}
        target=${EXTERNAL_LINK_TARGET}
        rel=${buildExternalLinkRel()}
        >${feedback.docsLabel}</a
      >
    </div>
  `;
}

function renderAdvancedSettings(state: AppViewState) {
  return html`
    <details class="login-gate__advanced" ?open=${state.loginShowAdvanced}>
      <summary
        @click=${() => {
          state.loginShowAdvanced = !state.loginShowAdvanced;
        }}
      >
        ${t("login.advanced.title")}
      </summary>
      <div class="login-gate__advanced-body">
        <label class="field">
          <span>${t("overview.access.wsUrl")}</span>
          <input
            .value=${state.settings.gatewayUrl}
            @input=${(e: Event) => {
              const v = (e.target as HTMLInputElement).value;
              state.applySettings({ ...state.settings, gatewayUrl: v });
            }}
            placeholder="ws://127.0.0.1:18789"
          />
        </label>
        <label class="field">
          <span>${t("overview.access.token")}</span>
          <div class="login-gate__secret-row">
            <input
              type=${state.loginShowGatewayToken ? "text" : "password"}
              autocomplete="off"
              spellcheck="false"
              .value=${state.settings.token}
              @input=${(e: Event) => {
                const v = (e.target as HTMLInputElement).value;
                state.applySettings({ ...state.settings, token: v });
              }}
              placeholder=${t("login.advanced.tokenPlaceholder")}
            />
            <button
              type="button"
              class="btn btn--icon ${state.loginShowGatewayToken ? "active" : ""}"
              title=${state.loginShowGatewayToken ? t("login.hideToken") : t("login.showToken")}
              aria-label=${t("login.toggleTokenVisibility")}
              aria-pressed=${state.loginShowGatewayToken}
              @click=${() => {
                state.loginShowGatewayToken = !state.loginShowGatewayToken;
              }}
            >
              ${state.loginShowGatewayToken ? icons.eye : icons.eyeOff}
            </button>
          </div>
        </label>
      </div>
    </details>
  `;
}

export function renderLoginGate(state: AppViewState) {
  const basePath = normalizeBasePath(state.basePath ?? "");
  const faviconSrc = agentLogoUrl(basePath);
  const failure = resolveLoginFailureFeedback({
    connected: state.connected,
    lastError: state.lastError,
    lastErrorCode: state.lastErrorCode,
    hasToken: Boolean(state.settings.token.trim()),
    hasPassword: Boolean(state.password.trim()),
    hasUsername: Boolean(state.loginUsername.trim()),
  });

  return html`
    <div class="login-gate">
      <div class="login-gate__shell">
        <div class="login-gate__brand-panel">
          <img class="login-gate__logo" src=${faviconSrc} alt=${t("brand.productTitle")} />
          <div class="login-gate__brand-name">IntelliSoins</div>
          <div class="login-gate__brand-tagline">${t("login.brandTagline")}</div>
        </div>
        <div class="login-gate__card">
          <div class="login-gate__header">
            <div class="login-gate__title">${t("login.title")}</div>
            <div class="login-gate__sub">${t("login.subtitle")}</div>
          </div>
          <div class="login-gate__form">
            <label class="field">
              <span>${t("login.username")}</span>
              <input
                autocomplete="username"
                spellcheck="false"
                .value=${state.loginUsername}
                @input=${(e: Event) => {
                  state.loginUsername = (e.target as HTMLInputElement).value;
                }}
                placeholder=${t("login.usernamePlaceholder")}
                @keydown=${(e: KeyboardEvent) => {
                  if (e.key === "Enter") {
                    state.connect();
                  }
                }}
              />
            </label>
            <label class="field">
              <span>${t("login.password")}</span>
              <div class="login-gate__secret-row">
                <input
                  type=${state.loginShowGatewayPassword ? "text" : "password"}
                  autocomplete="current-password"
                  spellcheck="false"
                  .value=${state.password}
                  @input=${(e: Event) => {
                    state.password = (e.target as HTMLInputElement).value;
                  }}
                  placeholder=${t("login.passwordPlaceholder")}
                  @keydown=${(e: KeyboardEvent) => {
                    if (e.key === "Enter") {
                      state.connect();
                    }
                  }}
                />
                <button
                  type="button"
                  class="btn btn--icon ${state.loginShowGatewayPassword ? "active" : ""}"
                  title=${state.loginShowGatewayPassword
                    ? t("login.hidePassword")
                    : t("login.showPassword")}
                  aria-label=${t("login.togglePasswordVisibility")}
                  aria-pressed=${state.loginShowGatewayPassword}
                  @click=${() => {
                    state.loginShowGatewayPassword = !state.loginShowGatewayPassword;
                  }}
                >
                  ${state.loginShowGatewayPassword ? icons.eye : icons.eyeOff}
                </button>
              </div>
            </label>
            <label class="field">
              <span>${t("login.mfaCode")}</span>
              <input
                class="login-gate__mfa-input"
                inputmode="numeric"
                autocomplete="one-time-code"
                maxlength="6"
                pattern="[0-9]*"
                .value=${state.loginMfaCode}
                @input=${(e: Event) => {
                  const raw = (e.target as HTMLInputElement).value.replace(/\D/g, "").slice(0, 6);
                  state.loginMfaCode = raw;
                  (e.target as HTMLInputElement).value = raw;
                }}
                placeholder=${t("login.mfaPlaceholder")}
                @keydown=${(e: KeyboardEvent) => {
                  if (e.key === "Enter") {
                    state.connect();
                  }
                }}
              />
            </label>
            <button class="btn primary login-gate__connect" @click=${() => state.connect()}>
              ${t("login.connect")}
            </button>
          </div>
          ${failure ? renderLoginFailure(failure) : ""} ${renderAdvancedSettings(state)}
        </div>
      </div>
    </div>
  `;
}
