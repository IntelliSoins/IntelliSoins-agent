/**
 * Gateway handler for browser.request, including optional node-host proxy
 * dispatch and local Browser control route dispatch.
 */
import crypto from "node:crypto";
import { clampTimerTimeoutMs } from "openclaw/plugin-sdk/number-runtime";
import {
  normalizeLowercaseStringOrEmpty,
  normalizeOptionalString,
} from "openclaw/plugin-sdk/string-coerce-runtime";
import { setSharedNodeRegistry } from "../browser-control-state.js";
import type { ResolvedBrowserConfig } from "../browser/config.js";
import {
  ErrorCodes,
  applyBrowserProxyPaths,
  createBrowserControlContext,
  createBrowserRouteDispatcher,
  errorShape,
  getRuntimeConfig,
  isNodeCommandAllowed,
  isPersistentBrowserProfileMutation,
  persistBrowserProxyFiles,
  resolveNodeCommandAllowlist,
  resolveProfile,
  resolveRequestedBrowserProfile,
  respondUnavailableOnNodeInvokeError,
  safeParseJson,
  startBrowserControlServiceFromConfig,
  withTimeout,
  type GatewayRequestHandlers,
  type NodeSession,
  type OpenClawConfig,
} from "../core-api.js";

type BrowserRequestParams = {
  method?: string;
  path?: string;
  query?: Record<string, unknown>;
  body?: unknown;
  timeoutMs?: number;
};

type BrowserProxyFile = {
  path: string;
  base64: string;
  mimeType?: string;
};

type BrowserProxyResult = {
  result: unknown;
  files?: BrowserProxyFile[];
};

function isBrowserNode(node: NodeSession) {
  const caps = Array.isArray(node.caps) ? node.caps : [];
  const commands = Array.isArray(node.commands) ? node.commands : [];
  return caps.includes("browser") || commands.includes("browser.proxy");
}

function normalizeNodeKey(value: string) {
  return normalizeLowercaseStringOrEmpty(value).replace(/[^a-z0-9]+/g, "");
}

function resolveBrowserNode(nodes: NodeSession[], query: string): NodeSession | null {
  const q = normalizeOptionalString(query) ?? "";
  if (!q) {
    return null;
  }
  const qNorm = normalizeNodeKey(q);
  const matches = nodes.filter((node) => {
    if (node.nodeId === q) {
      return true;
    }
    if (typeof node.remoteIp === "string" && node.remoteIp === q) {
      return true;
    }
    const name = typeof node.displayName === "string" ? node.displayName : "";
    if (name && normalizeNodeKey(name) === qNorm) {
      return true;
    }
    if (q.length >= 6 && node.nodeId.startsWith(q)) {
      return true;
    }
    return false;
  });
  if (matches.length === 1) {
    return matches[0] ?? null;
  }
  if (matches.length === 0) {
    return null;
  }
  throw new Error(
    `ambiguous node: ${q} (matches: ${matches
      .map((node) => node.displayName || node.remoteIp || node.nodeId)
      .join(", ")})`,
  );
}

function resolveBrowserNodeTarget(params: {
  cfg: OpenClawConfig;
  nodes: NodeSession[];
}): NodeSession | null {
  const policy = params.cfg.gateway?.nodes?.browser;
  const mode = policy?.mode ?? "auto";
  if (mode === "off") {
    return null;
  }
  const browserNodes = params.nodes.filter((node) => isBrowserNode(node));
  if (browserNodes.length === 0) {
    if (normalizeOptionalString(policy?.node)) {
      throw new Error("No connected browser-capable nodes.");
    }
    return null;
  }
  const requested = normalizeOptionalString(policy?.node) ?? "";
  if (requested) {
    const resolved = resolveBrowserNode(browserNodes, requested);
    if (!resolved) {
      throw new Error(`Configured browser node not connected: ${requested}`);
    }
    return resolved;
  }
  if (mode === "manual") {
    return null;
  }
  if (browserNodes.length === 1) {
    return browserNodes[0] ?? null;
  }
  return null;
}

async function persistProxyFiles(files: BrowserProxyFile[] | undefined) {
  return await persistBrowserProxyFiles(files);
}

function applyProxyPaths(result: unknown, mapping: Map<string, string>) {
  applyBrowserProxyPaths(result, mapping);
}

/** Handles one browser.request gateway call and streams a success/error response. */
export async function handleBrowserGatewayRequest({
  params,
  respond,
  context,
}: Parameters<GatewayRequestHandlers["browser.request"]>[0]) {
  const typed = params as BrowserRequestParams;
  const methodRaw = (normalizeOptionalString(typed.method) ?? "").toUpperCase();
  const path = normalizeOptionalString(typed.path) ?? "";
  const query = typed.query && typeof typed.query === "object" ? typed.query : undefined;
  const body = typed.body;
  const timeoutMs = clampTimerTimeoutMs(typed.timeoutMs);

  if (!methodRaw || !path) {
    respond(
      false,
      undefined,
      errorShape(ErrorCodes.INVALID_REQUEST, "method and path are required"),
    );
    return;
  }
  if (methodRaw !== "GET" && methodRaw !== "POST" && methodRaw !== "DELETE") {
    respond(
      false,
      undefined,
      errorShape(ErrorCodes.INVALID_REQUEST, "method must be GET, POST, or DELETE"),
    );
    return;
  }
  if (isPersistentBrowserProfileMutation(methodRaw, path)) {
    respond(
      false,
      undefined,
      errorShape(
        ErrorCodes.INVALID_REQUEST,
        "browser.request cannot mutate persistent browser profiles",
      ),
    );
    return;
  }

  const cfg = getRuntimeConfig();
  setSharedNodeRegistry(context.nodeRegistry);

  const initialReady = await startBrowserControlServiceFromConfig();
  if (initialReady && typeof initialReady === "object" && "resolved" in initialReady) {
    const resolvedConfig = (initialReady as { resolved: ResolvedBrowserConfig }).resolved;
    const profileName =
      resolveRequestedBrowserProfile({ query, body }) ?? resolvedConfig.defaultProfile;
    const profile = resolveProfile(resolvedConfig, profileName);
    if (profile && profile.driver === "webkit-native") {
      const companion = context.nodeRegistry.get("openclaw-macos");
      if (!companion) {
        respond(
          false,
          undefined,
          errorShape(
            ErrorCodes.UNAVAILABLE,
            "macOS companion application (openclaw-macos) is not connected",
          ),
        );
        return;
      }

      interface CompanionWsClient {
        socket: { send(data: string): void };
        pendingRequests?: Map<
          string,
          {
            resolve: (value: unknown) => void;
            reject: (reason: Error) => void;
            timer: NodeJS.Timeout;
          }
        >;
      }

      interface BrowserRequestBody {
        url?: string;
        kind?: string;
        fn?: string;
        targetId?: string;
      }

      const client = companion.client as unknown as CompanionWsClient;
      if (!client.pendingRequests) {
        client.pendingRequests = new Map();
      }

      const bodyData = body as BrowserRequestBody | null | undefined;
      const requestId = crypto.randomUUID();
      let reqFrame: {
        type: "req";
        id: string;
        method: string;
        params: Record<string, unknown>;
      } | null = null;

      if (path === "/navigate" && methodRaw === "POST") {
        const bodyUrl = bodyData?.url;
        if (!bodyUrl) {
          respond(
            false,
            undefined,
            errorShape(ErrorCodes.INVALID_REQUEST, "Missing required param 'url'"),
          );
          return;
        }
        reqFrame = {
          type: "req",
          id: requestId,
          method: "browser.navigate",
          params: { url: bodyUrl },
        };
      } else if (path === "/act" && methodRaw === "POST" && bodyData?.kind === "evaluate") {
        const script = bodyData?.fn;
        if (!script) {
          respond(
            false,
            undefined,
            errorShape(ErrorCodes.INVALID_REQUEST, "Missing required param 'fn'"),
          );
          return;
        }
        reqFrame = {
          type: "req",
          id: requestId,
          method: "browser.evaluate",
          params: { script },
        };
      } else if (
        path === "/status" ||
        path === "/profiles" ||
        path === "/start" ||
        path === "/stop"
      ) {
        // Fall through to normal local routing
      } else {
        respond(
          false,
          undefined,
          errorShape(
            ErrorCodes.INVALID_REQUEST,
            `Unsupported operation '${methodRaw} ${path}' for webkit-native driver`,
          ),
        );
        return;
      }

      if (reqFrame) {
        const promise = new Promise((resolve, reject) => {
          const timer = setTimeout(() => {
            client.pendingRequests?.delete(requestId);
            reject(new Error("macOS companion webkit-native request timed out"));
          }, timeoutMs || 30000);

          client.pendingRequests?.set(requestId, {
            resolve,
            reject,
            timer,
          });
        });

        try {
          client.socket.send(JSON.stringify(reqFrame));
        } catch (err) {
          client.pendingRequests?.delete(requestId);
          respond(
            false,
            undefined,
            errorShape(
              ErrorCodes.UNAVAILABLE,
              `Failed to send request to macOS companion over WebSocket: ${String(err)}`,
            ),
          );
          return;
        }

        try {
          const response = (await promise) as {
            ok: boolean;
            payload?: { result?: unknown };
            error?: { message?: string };
          };
          if (response.ok) {
            const payload = response.payload;
            if (path === "/navigate") {
              respond(true, {
                ok: true,
                targetId: bodyData?.targetId || "default",
                url: bodyData?.url,
              });
            } else if (path === "/act") {
              respond(true, {
                ok: true,
                targetId: bodyData?.targetId || "default",
                result: payload?.result,
              });
            } else {
              respond(true, payload);
            }
          } else {
            respond(
              false,
              undefined,
              errorShape(
                ErrorCodes.UNAVAILABLE,
                response.error?.message || "macOS companion request failed",
              ),
            );
          }
        } catch (err) {
          respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
        }
        return;
      }
    }
  }

  let nodeTarget: NodeSession | null;
  try {
    nodeTarget = resolveBrowserNodeTarget({
      cfg,
      nodes: context.nodeRegistry.listConnected(),
    });
  } catch (err) {
    respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
    return;
  }

  if (nodeTarget) {
    const allowlist = resolveNodeCommandAllowlist(cfg, nodeTarget);
    const allowed = isNodeCommandAllowed({
      command: "browser.proxy",
      declaredCommands: nodeTarget.commands,
      allowlist,
    });
    if (!allowed.ok) {
      const platform = nodeTarget.platform ?? "unknown";
      const hint = `node command not allowed: ${allowed.reason} (platform: ${platform}, command: browser.proxy)`;
      respond(
        false,
        undefined,
        errorShape(ErrorCodes.INVALID_REQUEST, hint, {
          details: { reason: allowed.reason, command: "browser.proxy" },
        }),
      );
      return;
    }

    const proxyParams = {
      method: methodRaw,
      path,
      query,
      body,
      timeoutMs,
      profile: resolveRequestedBrowserProfile({ query, body }),
    };
    const res = await context.nodeRegistry.invoke({
      nodeId: nodeTarget.nodeId,
      command: "browser.proxy",
      params: proxyParams,
      timeoutMs,
      idempotencyKey: crypto.randomUUID(),
    });
    if (!respondUnavailableOnNodeInvokeError(respond, res)) {
      return;
    }
    const payload = res.payloadJSON ? safeParseJson(res.payloadJSON) : res.payload;
    const proxy = payload && typeof payload === "object" ? (payload as BrowserProxyResult) : null;
    if (!proxy || !("result" in proxy)) {
      respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, "browser proxy failed"));
      return;
    }
    const mapping = await persistProxyFiles(proxy.files);
    applyProxyPaths(proxy.result, mapping);
    respond(true, proxy.result);
    return;
  }

  const ready = await startBrowserControlServiceFromConfig();
  if (!ready) {
    respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, "browser control is disabled"));
    return;
  }

  let dispatcher;
  try {
    dispatcher = createBrowserRouteDispatcher(createBrowserControlContext());
  } catch (err) {
    respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
    return;
  }

  let result;
  try {
    result = timeoutMs
      ? await withTimeout(
          (signal) =>
            dispatcher.dispatch({
              method: methodRaw,
              path,
              query,
              body,
              signal,
            }),
          timeoutMs,
          "browser request",
        )
      : await dispatcher.dispatch({
          method: methodRaw,
          path,
          query,
          body,
        });
  } catch (err) {
    respond(false, undefined, errorShape(ErrorCodes.UNAVAILABLE, String(err)));
    return;
  }

  if (result.status >= 400) {
    const message =
      result.body && typeof result.body === "object" && "error" in result.body
        ? String((result.body as { error?: unknown }).error)
        : `browser request failed (${result.status})`;
    const code = result.status >= 500 ? ErrorCodes.UNAVAILABLE : ErrorCodes.INVALID_REQUEST;
    respond(false, undefined, errorShape(code, message, { details: result.body }));
    return;
  }

  respond(true, result.body);
}

/** Gateway request handler map contributed by the Browser plugin. */
export const browserHandlers: GatewayRequestHandlers = {
  "browser.request": handleBrowserGatewayRequest,
};
