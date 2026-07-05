// Mlx tests cover model-behavior heuristics.
import { describe, expect, it } from "vitest";
import { enrichMlxModelDefinition, isMlxVisionModelId } from "./model-behavior.js";

describe("mlx model behavior", () => {
  it("detects common MLX vision model ids", () => {
    expect(isMlxVisionModelId("mlx-community/Qwen2-VL-7B-Instruct-4bit")).toBe(true);
    expect(isMlxVisionModelId("mlx-community/Qwen3.5-9B-MLX-4bit")).toBe(true);
    expect(isMlxVisionModelId("mlx-community/Qwen3-8B-4bit")).toBe(false);
  });

  it("adds tool and prompt-cache compat for omlx backends", () => {
    const enriched = enrichMlxModelDefinition(
      {
        id: "Qwen3.5-9B-MLX-4bit",
        name: "Qwen3.5-9B-MLX-4bit",
        reasoning: true,
        input: ["text"],
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 131072,
        maxTokens: 8192,
      },
      "omlx",
    );

    expect(enriched.input).toEqual(["text", "image"]);
    expect(enriched.compat).toMatchObject({
      supportsTools: true,
      supportsPromptCacheKey: true,
      thinkingFormat: "qwen-chat-template",
    });
  });

  it("skips prompt-cache compat for basic mlx-lm servers", () => {
    const enriched = enrichMlxModelDefinition(
      {
        id: "mlx-community/Qwen3-30B-A3B-6bit",
        name: "mlx-community/Qwen3-30B-A3B-6bit",
        reasoning: false,
        input: ["text"],
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 131072,
        maxTokens: 8192,
      },
      "mlx-lm",
    );

    expect(enriched.compat?.supportsPromptCacheKey).toBeUndefined();
    expect(enriched.compat?.supportsTools).toBe(true);
  });
});
