// Mlx tests cover provider discovery.contract plugin behavior.
import { fileURLToPath } from "node:url";
import { registerSingleProviderPlugin } from "openclaw/plugin-sdk/plugin-test-runtime";
import { describeMlxProviderDiscoveryContract } from "openclaw/plugin-sdk/provider-test-contracts";
import { describe, expect, it } from "vitest";
import mlxPlugin from "./index.js";

describeMlxProviderDiscoveryContract({
  load: () => import("./index.js"),
  apiModuleId: fileURLToPath(new URL("./api.js", import.meta.url)),
});

describe("MLX provider registration", () => {
  it("exposes the binary thinking profile hook", async () => {
    const provider = await registerSingleProviderPlugin(mlxPlugin);

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
});
