// Mlx plugin module implements MLX model heuristics and compat shaping.
import type { ModelDefinitionConfig } from "openclaw/plugin-sdk/provider-model-shared";
import type { MlxBackendId } from "./defaults.js";
import { resolveMlxBackendPreset } from "./defaults.js";

const MLX_VISION_MODEL_PATTERN =
  /(?:^|[-_/])(?:vl|vlm|vision|llava|pixtral|gemma-?4|qwen2[-_.]?vl|qwen3[-_.]?5|qwen3\.5|idefics|molmo|minicpm[-_.]?v|internvl|deepseek[-_.]?vl|llama[-_.]?3\.2[-_.]?vision)(?:[-_/]|$)/i;

const MLX_QWEN_MODEL_PATTERN = /\bqwen(?:2|2\.5|3|3\.5)?(?:[-_.]|$)/i;

const MLX_NEMOTRON_MODEL_PATTERN = /\bnemotron(?:-3(?:[-_](?:nano|super|ultra))?)?\b/i;

export function isMlxVisionModelId(modelId: string): boolean {
  return MLX_VISION_MODEL_PATTERN.test(modelId);
}

export function isMlxQwenModelId(modelId: string): boolean {
  return MLX_QWEN_MODEL_PATTERN.test(modelId);
}

export function isMlxNemotronThinkingModelId(modelId: string): boolean {
  return MLX_NEMOTRON_MODEL_PATTERN.test(modelId);
}

export function enrichMlxModelDefinition(
  model: ModelDefinitionConfig,
  backendId: MlxBackendId = "custom",
): ModelDefinitionConfig {
  const backend = resolveMlxBackendPreset(backendId);
  const vision = isMlxVisionModelId(model.id);
  const input = vision ? (["text", "image"] as const) : (["text"] as const);
  const compat: NonNullable<ModelDefinitionConfig["compat"]> = {
    ...model.compat,
    supportedParameters: ["tools", "tool_choice"],
  };
  if (backend.supportsPromptCacheKey) {
    compat.supportsPromptCacheKey = true;
  }
  if (isMlxQwenModelId(model.id) && model.reasoning !== false) {
    compat.thinkingFormat = "qwen-chat-template";
  }
  return {
    ...model,
    input: [...input],
    compat,
  };
}
