// Mlx plugin module implements stream behavior.
import type { StreamFn } from "openclaw/plugin-sdk/agent-core";
import type { ProviderWrapStreamFnContext } from "openclaw/plugin-sdk/plugin-entry";
import { normalizeProviderId } from "openclaw/plugin-sdk/provider-model-shared";
import {
  createPayloadPatchStreamWrapper,
  isOpenAICompatibleThinkingEnabled,
} from "openclaw/plugin-sdk/provider-stream-shared";
import { isMlxNemotronThinkingModelId } from "./model-behavior.js";
import {
  resolveMlxQwenThinkingFormatFromCompat,
  type MlxQwenThinkingFormat,
} from "./thinking-policy.js";

type MlxThinkingLevel = ProviderWrapStreamFnContext["thinkingLevel"];

function isMlxProviderId(providerId: string): boolean {
  return normalizeProviderId(providerId) === "mlx";
}

function setQwenChatTemplateThinking(payload: Record<string, unknown>, enabled: boolean): void {
  const existing = payload.chat_template_kwargs;
  if (existing && typeof existing === "object" && !Array.isArray(existing)) {
    const next: Record<string, unknown> = {
      ...(existing as Record<string, unknown>),
      enable_thinking: enabled,
    };
    if (!Object.hasOwn(next, "preserve_thinking")) {
      next.preserve_thinking = true;
    }
    payload.chat_template_kwargs = next;
    return;
  }
  payload.chat_template_kwargs = {
    enable_thinking: enabled,
    preserve_thinking: true,
  };
}

function setNemotronThinkingOffChatTemplateKwargs(payload: Record<string, unknown>): void {
  const defaults = {
    enable_thinking: false,
    force_nonempty_content: true,
  };
  const existing = payload.chat_template_kwargs;
  payload.chat_template_kwargs =
    existing && typeof existing === "object" && !Array.isArray(existing)
      ? {
          ...defaults,
          ...(existing as Record<string, unknown>),
        }
      : defaults;
}

export function wrapMlxProviderStream(
  ctx: ProviderWrapStreamFnContext,
  baseStreamFn: StreamFn | undefined,
): StreamFn {
  const providerId = ctx.model?.provider;
  if (typeof providerId !== "string" || !isMlxProviderId(providerId)) {
    return baseStreamFn ?? ctx.streamFn;
  }
  const qwenFormat = resolveMlxQwenThinkingFormatFromCompat(ctx.model?.compat);
  if (qwenFormat) {
    return createPayloadPatchStreamWrapper(
      baseStreamFn ?? ctx.streamFn,
      ({ payload: payloadObj, options }) => {
        const enableThinking = isOpenAICompatibleThinkingEnabled({
          thinkingLevel: ctx.thinkingLevel,
          options,
        });
        if (qwenFormat === "chat-template") {
          setQwenChatTemplateThinking(payloadObj, enableThinking);
          return;
        }
        payloadObj.enable_thinking = enableThinking;
      },
    );
  }
  if (
    ctx.model?.api === "openai-completions" &&
    typeof ctx.model.id === "string" &&
    isMlxNemotronThinkingModelId(ctx.model.id)
  ) {
    return createPayloadPatchStreamWrapper(
      baseStreamFn ?? ctx.streamFn,
      ({ payload: payloadObj, options }) => {
        const enableThinking = isOpenAICompatibleThinkingEnabled({
          thinkingLevel: ctx.thinkingLevel as MlxThinkingLevel,
          options,
        });
        if (!enableThinking) {
          setNemotronThinkingOffChatTemplateKwargs(payloadObj);
        }
      },
    );
  }
  return baseStreamFn ?? ctx.streamFn;
}
