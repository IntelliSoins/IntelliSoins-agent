// Mlx plugin module implements thinking policy behavior.
import type {
  ProviderDefaultThinkingPolicyContext,
  ProviderThinkingProfile,
} from "openclaw/plugin-sdk/plugin-entry";
import { normalizeProviderId } from "openclaw/plugin-sdk/provider-model-shared";
import { isMlxNemotronThinkingModelId, isMlxQwenModelId } from "./model-behavior.js";

export type MlxQwenThinkingFormat = "chat-template" | "top-level";

const MLX_BINARY_THINKING_PROFILE = {
  levels: [{ id: "off" }, { id: "low", label: "on" }],
  defaultLevel: "off",
} satisfies ProviderThinkingProfile;

export function normalizeMlxQwenThinkingFormat(value: unknown): MlxQwenThinkingFormat | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const normalized = value.trim().toLowerCase().replace(/_/g, "-");
  if (
    normalized === "chat-template" ||
    normalized === "chat-template-kwargs" ||
    normalized === "qwen-chat-template"
  ) {
    return "chat-template";
  }
  if (
    normalized === "top-level" ||
    normalized === "enable-thinking" ||
    normalized === "request-body" ||
    normalized === "qwen"
  ) {
    return "top-level";
  }
  return undefined;
}

export function resolveMlxQwenThinkingFormatFromCompat(
  compat?: ProviderDefaultThinkingPolicyContext["compat"],
): MlxQwenThinkingFormat | undefined {
  return normalizeMlxQwenThinkingFormat(compat?.thinkingFormat);
}

export function resolveThinkingProfile(
  ctx: ProviderDefaultThinkingPolicyContext,
): ProviderThinkingProfile | null {
  if (normalizeProviderId(ctx.provider) !== "mlx") {
    return null;
  }
  if (ctx.reasoning === false) {
    return null;
  }
  const qwenFormat = resolveMlxQwenThinkingFormatFromCompat(ctx.compat);
  if (qwenFormat || (ctx.reasoning === true && isMlxNemotronThinkingModelId(ctx.modelId))) {
    return MLX_BINARY_THINKING_PROFILE;
  }
  if (ctx.reasoning === true && isMlxQwenModelId(ctx.modelId)) {
    return MLX_BINARY_THINKING_PROFILE;
  }
  return null;
}
