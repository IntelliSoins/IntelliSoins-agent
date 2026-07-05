// Mlx plugin module implements defaults behavior.
export const MLX_PROVIDER_ID = "mlx";

export const MLX_DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1";
export const MLX_PROVIDER_LABEL = "MLX";
export const MLX_DEFAULT_API_KEY_ENV_VAR = "MLX_API_KEY";
export const MLX_BACKEND_ENV_VAR = "MLX_BACKEND";
export const MLX_MODEL_PLACEHOLDER = "mlx-community/Qwen3-8B-4bit";

export const MLX_BACKEND_IDS = [
  "omlx",
  "vllm-mlx",
  "vmlx",
  "mlx-lm",
  "mlx-openai-server",
  "mlxcel",
  "custom",
] as const;

export type MlxBackendId = (typeof MLX_BACKEND_IDS)[number];

export type MlxBackendPreset = {
  id: MlxBackendId;
  label: string;
  defaultBaseUrl: string;
  apiKeyEnvVar: string;
  supportsPromptCacheKey: boolean;
  modelPlaceholder: string;
};

export const MLX_BACKEND_PRESETS: Record<MlxBackendId, MlxBackendPreset> = {
  omlx: {
    id: "omlx",
    label: "oMLX",
    defaultBaseUrl: "http://127.0.0.1:8000/v1",
    apiKeyEnvVar: "OMLX_API_KEY",
    supportsPromptCacheKey: true,
    modelPlaceholder: "Qwen3.5-9B-MLX-4bit",
  },
  "vllm-mlx": {
    id: "vllm-mlx",
    label: "vLLM-MLX",
    defaultBaseUrl: "http://127.0.0.1:8000/v1",
    apiKeyEnvVar: "VLLM_MLX_API_KEY",
    supportsPromptCacheKey: true,
    modelPlaceholder: "mlx-community/Qwen3-8B-4bit",
  },
  vmlx: {
    id: "vmlx",
    label: "vMLX",
    defaultBaseUrl: "http://127.0.0.1:8000/v1",
    apiKeyEnvVar: "VMLX_API_KEY",
    supportsPromptCacheKey: true,
    modelPlaceholder: "mlx-community/Qwen3-8B-4bit",
  },
  "mlx-lm": {
    id: "mlx-lm",
    label: "mlx-lm",
    defaultBaseUrl: "http://127.0.0.1:8080/v1",
    apiKeyEnvVar: "MLX_API_KEY",
    supportsPromptCacheKey: false,
    modelPlaceholder: "mlx-community/Qwen3-30B-A3B-6bit",
  },
  "mlx-openai-server": {
    id: "mlx-openai-server",
    label: "mlx-openai-server",
    defaultBaseUrl: "http://127.0.0.1:8000/v1",
    apiKeyEnvVar: "MLX_OPENAI_SERVER_API_KEY",
    supportsPromptCacheKey: true,
    modelPlaceholder: "mlx-community/Llama-3.2-3B-Instruct-4bit",
  },
  mlxcel: {
    id: "mlxcel",
    label: "mlxcel",
    defaultBaseUrl: "http://127.0.0.1:8097/v1",
    apiKeyEnvVar: "MLXCEL_API_KEY",
    supportsPromptCacheKey: true,
    modelPlaceholder: "mlx-community/Qwen3.5-9B-MLX-4bit",
  },
  custom: {
    id: "custom",
    label: "Custom MLX server",
    defaultBaseUrl: MLX_DEFAULT_BASE_URL,
    apiKeyEnvVar: MLX_DEFAULT_API_KEY_ENV_VAR,
    supportsPromptCacheKey: true,
    modelPlaceholder: MLX_MODEL_PLACEHOLDER,
  },
};

export function normalizeMlxBackendId(value: unknown): MlxBackendId {
  if (typeof value !== "string") {
    return "custom";
  }
  const normalized = value.trim().toLowerCase().replace(/_/g, "-");
  if ((MLX_BACKEND_IDS as readonly string[]).includes(normalized)) {
    return normalized as MlxBackendId;
  }
  return "custom";
}

export function resolveMlxBackendPreset(backendId: MlxBackendId = "custom"): MlxBackendPreset {
  return MLX_BACKEND_PRESETS[backendId] ?? MLX_BACKEND_PRESETS.custom;
}

export function resolveMlxBackendFromEnv(env: NodeJS.ProcessEnv = process.env): MlxBackendId {
  return normalizeMlxBackendId(env[MLX_BACKEND_ENV_VAR]);
}

export function resolveMlxDefaultBaseUrl(env: NodeJS.ProcessEnv = process.env): string {
  return resolveMlxBackendPreset(resolveMlxBackendFromEnv(env)).defaultBaseUrl;
}
