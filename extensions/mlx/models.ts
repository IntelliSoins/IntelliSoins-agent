// Mlx plugin module implements models behavior.
import type { OpenClawConfig } from "openclaw/plugin-sdk/config-contracts";
import { discoverOpenAICompatibleLocalModels } from "openclaw/plugin-sdk/provider-setup";
import {
  MLX_DEFAULT_BASE_URL,
  MLX_PROVIDER_LABEL,
  resolveMlxBackendFromEnv,
  resolveMlxDefaultBaseUrl,
  type MlxBackendId,
} from "./defaults.js";
import { enrichMlxModelDefinition } from "./model-behavior.js";

type ModelsConfig = NonNullable<OpenClawConfig["models"]>;
type ProviderConfig = NonNullable<ModelsConfig["providers"]>[string];

export async function buildMlxProvider(params?: {
  baseUrl?: string;
  apiKey?: string;
  backend?: MlxBackendId;
  env?: NodeJS.ProcessEnv;
}): Promise<ProviderConfig> {
  const env = params?.env ?? process.env;
  const backend = params?.backend ?? resolveMlxBackendFromEnv(env);
  const baseUrl = (
    params?.baseUrl?.trim() ||
    resolveMlxDefaultBaseUrl(env) ||
    MLX_DEFAULT_BASE_URL
  ).replace(/\/+$/, "");
  const models = await discoverOpenAICompatibleLocalModels({
    baseUrl,
    apiKey: params?.apiKey,
    label: MLX_PROVIDER_LABEL,
    env,
  });
  return {
    baseUrl,
    api: "openai-completions",
    models: models.map((model) => enrichMlxModelDefinition(model, backend)),
  };
}
