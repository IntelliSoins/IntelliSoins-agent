// Qqbot plugin module implements sqlite state behavior.
import crypto from "node:crypto";
import type {
  OpenKeyedStoreOptions,
  PluginStateSyncKeyedStore,
} from "openclaw/plugin-sdk/plugin-state-runtime";
import { resolveScopedStateEnv } from "openclaw/plugin-sdk/scoped-state-env";
import { getQQBotRuntime } from "../../bridge/runtime.js";

type QQBotSyncStoreOptions = OpenKeyedStoreOptions & {
  stateDir?: string;
};

export function openQQBotSyncKeyedStore<T>(
  options: QQBotSyncStoreOptions,
): PluginStateSyncKeyedStore<T> {
  const env = resolveScopedStateEnv({ env: options.env, stateDir: options.stateDir });
  return getQQBotRuntime().state.openSyncKeyedStore<T>({
    namespace: options.namespace,
    maxEntries: options.maxEntries,
    ...(options.defaultTtlMs != null ? { defaultTtlMs: options.defaultTtlMs } : {}),
    ...(env ? { env } : {}),
  });
}

export function buildQQBotStateKey(...parts: string[]): string {
  return crypto.createHash("sha256").update(JSON.stringify(parts)).digest("hex");
}
