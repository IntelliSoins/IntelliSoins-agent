// Mlx tests cover index plugin behavior.
import { registerSingleProviderPlugin } from "openclaw/plugin-sdk/plugin-test-runtime";
import { describe, expect, it } from "vitest";
import plugin from "./index.js";

describe("mlx provider plugin", () => {
  it("owns OpenAI-compatible replay without dropping reasoning history", async () => {
    const provider = await registerSingleProviderPlugin(plugin);
    const policy = provider.buildReplayPolicy?.({
      provider: "mlx",
      modelApi: "openai-completions",
      modelId: "mlx-community/DeepSeek-R1-0528-Qwen3-8B-4bit",
    } as never);

    expect(policy).toMatchObject({
      sanitizeToolCallIds: true,
      toolCallIdMode: "strict",
      applyAssistantFirstOrderingFix: true,
      validateGeminiTurns: true,
      validateAnthropicTurns: true,
    });
    expect(policy).not.toHaveProperty("dropReasoningFromHistory");
  });

  it("exposes the binary thinking profile hook for Qwen MLX models", async () => {
    const provider = await registerSingleProviderPlugin(plugin);

    expect(
      provider.resolveThinkingProfile?.({
        provider: "mlx",
        modelId: "mlx-community/Qwen3-8B-4bit",
        reasoning: true,
        compat: { thinkingFormat: "qwen-chat-template" },
      }),
    ).toEqual({
      levels: [{ id: "off" }, { id: "low", label: "on" }],
      defaultLevel: "off",
    });
  });

  it("routes legacy omlx-local hook aliases to the mlx provider", async () => {
    const provider = await registerSingleProviderPlugin(plugin);
    expect(provider.hookAliases).toContain("omlx-local");
  });
});
