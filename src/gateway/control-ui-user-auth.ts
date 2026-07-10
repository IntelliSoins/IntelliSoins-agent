// Control UI per-user account authentication with optional TOTP MFA.
import { normalizeOptionalString } from "@openclaw/normalization-core/string-coerce";
import { verifyTotpCode } from "../security/totp.js";
import type { AuthRateLimiter } from "./auth-rate-limit.js";
import { AUTH_RATE_LIMIT_SCOPE_USER_ACCOUNT } from "./auth-rate-limit.js";
import type { GatewayAuthResult } from "./auth.js";
import {
  findControlUiUserByUsername,
  resolveControlUiUserTotpSecret,
  verifyControlUiUserPassword,
} from "./control-ui-users.sqlite.js";

export type ControlUiUserConnectAuth = {
  username?: string;
  password?: string;
  mfaCode?: string;
};

function hasUserAccountCredentials(connectAuth?: ControlUiUserConnectAuth | null): boolean {
  return Boolean(
    normalizeOptionalString(connectAuth?.username) &&
    normalizeOptionalString(connectAuth?.password),
  );
}

function rejectUserAuth(params: {
  reason: string;
  limiter?: AuthRateLimiter;
  ip?: string;
  recordFailure?: boolean;
}): GatewayAuthResult {
  if (params.recordFailure !== false) {
    params.limiter?.recordFailure(params.ip, AUTH_RATE_LIMIT_SCOPE_USER_ACCOUNT);
  }
  return { ok: false, reason: params.reason };
}

/** Authorize a Control UI connect attempt using per-user credentials and TOTP MFA. */
export function authorizeControlUiUserAccountAuth(params: {
  connectAuth?: ControlUiUserConnectAuth | null;
  limiter?: AuthRateLimiter;
  ip?: string;
  env?: NodeJS.ProcessEnv;
}): GatewayAuthResult | null {
  if (!hasUserAccountCredentials(params.connectAuth)) {
    return null;
  }
  const username = normalizeOptionalString(params.connectAuth?.username);
  const password = normalizeOptionalString(params.connectAuth?.password);
  const mfaCode = normalizeOptionalString(params.connectAuth?.mfaCode);
  if (!username || !password) {
    return rejectUserAuth({
      reason: "user_credentials_missing",
      limiter: params.limiter,
      ip: params.ip,
      recordFailure: false,
    });
  }

  const user = verifyControlUiUserPassword(username, password, { env: params.env });
  if (!user) {
    const exists = findControlUiUserByUsername(username, { env: params.env });
    return rejectUserAuth({
      reason: exists ? "user_password_mismatch" : "user_not_found",
      limiter: params.limiter,
      ip: params.ip,
    });
  }

  if (user.totpEnabled) {
    if (!mfaCode) {
      return rejectUserAuth({
        reason: "user_mfa_required",
        limiter: params.limiter,
        ip: params.ip,
        recordFailure: false,
      });
    }
    const totpSecret = resolveControlUiUserTotpSecret(user, params.env);
    if (!totpSecret || !verifyTotpCode(totpSecret, mfaCode)) {
      return rejectUserAuth({
        reason: "user_mfa_invalid",
        limiter: params.limiter,
        ip: params.ip,
      });
    }
  }

  params.limiter?.reset(params.ip, AUTH_RATE_LIMIT_SCOPE_USER_ACCOUNT);
  return { ok: true, method: "user-account", user: user.username };
}

/** Return true when connect auth carries explicit per-user credentials. */
export function hasExplicitUserAccountAuth(connectAuth?: ControlUiUserConnectAuth | null): boolean {
  return hasUserAccountCredentials(connectAuth);
}
