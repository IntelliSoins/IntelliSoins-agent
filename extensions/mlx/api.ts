// Mlx API module exposes the plugin public contract.
export {
  MLX_BACKEND_ENV_VAR,
  MLX_BACKEND_IDS,
  MLX_BACKEND_PRESETS,
  MLX_DEFAULT_API_KEY_ENV_VAR,
  MLX_DEFAULT_BASE_URL,
  MLX_MODEL_PLACEHOLDER,
  MLX_PROVIDER_ID,
  MLX_PROVIDER_LABEL,
  normalizeMlxBackendId,
  resolveMlxBackendFromEnv,
  resolveMlxBackendPreset,
  resolveMlxDefaultBaseUrl,
  type MlxBackendId,
  type MlxBackendPreset,
} from "./defaults.js";
export {
  enrichMlxModelDefinition,
  isMlxNemotronThinkingModelId,
  isMlxQwenModelId,
  isMlxVisionModelId,
} from "./model-behavior.js";
export { buildMlxProvider } from "./models.js";
export { wrapMlxProviderStream } from "./stream.js";
