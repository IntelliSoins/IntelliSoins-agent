// Mlx plugin entrypoint registers its OpenClaw integration.
import {
  definePluginEntry,
  type OpenClawPluginApi,
  type ProviderAuthMethodNonInteractiveContext,
} from "openclaw/plugin-sdk/plugin-entry";
import { buildProviderReplayFamilyHooks } from "openclaw/plugin-sdk/provider-model-shared";
import {
  MLX_DEFAULT_API_KEY_ENV_VAR,
  MLX_DEFAULT_BASE_URL,
  MLX_MODEL_PLACEHOLDER,
  MLX_PROVIDER_ID,
  MLX_PROVIDER_LABEL,
  buildMlxProvider,
} from "./api.js";
import { wrapMlxProviderStream } from "./stream.js";
import { resolveThinkingProfile } from "./thinking-policy.js";

async function loadProviderSetup() {
  return await import("openclaw/plugin-sdk/provider-setup");
}

export default definePluginEntry({
  id: MLX_PROVIDER_ID,
  name: "MLX Provider",
  description: "Bundled Apple Silicon MLX inference provider plugin",
  register(api: OpenClawPluginApi) {
    api.registerProvider({
      id: MLX_PROVIDER_ID,
      label: MLX_PROVIDER_LABEL,
      docsPath: "/providers/mlx",
      hookAliases: ["omlx-local"],
      envVars: [MLX_DEFAULT_API_KEY_ENV_VAR, "OMLX_API_KEY", "VLLM_MLX_API_KEY", "VMLX_API_KEY"],
      auth: [
        {
          id: "custom",
          label: MLX_PROVIDER_LABEL,
          hint: "Apple Silicon MLX server (oMLX, vLLM-MLX, vMLX, mlx-lm, …)",
          kind: "custom",
          run: async (ctx) => {
            const providerSetup = await loadProviderSetup();
            return await providerSetup.promptAndConfigureOpenAICompatibleSelfHostedProviderAuth({
              cfg: ctx.config,
              prompter: ctx.prompter,
              providerId: MLX_PROVIDER_ID,
              providerLabel: MLX_PROVIDER_LABEL,
              defaultBaseUrl: MLX_DEFAULT_BASE_URL,
              defaultApiKeyEnvVar: MLX_DEFAULT_API_KEY_ENV_VAR,
              modelPlaceholder: MLX_MODEL_PLACEHOLDER,
            });
          },
          runNonInteractive: async (ctx: ProviderAuthMethodNonInteractiveContext) => {
            const providerSetup = await loadProviderSetup();
            return await providerSetup.configureOpenAICompatibleSelfHostedProviderNonInteractive({
              ctx,
              providerId: MLX_PROVIDER_ID,
              providerLabel: MLX_PROVIDER_LABEL,
              defaultBaseUrl: MLX_DEFAULT_BASE_URL,
              defaultApiKeyEnvVar: MLX_DEFAULT_API_KEY_ENV_VAR,
              modelPlaceholder: MLX_MODEL_PLACEHOLDER,
            });
          },
        },
      ],
      catalog: {
        order: "late",
        run: async (ctx) => {
          const providerSetup = await loadProviderSetup();
          return await providerSetup.discoverOpenAICompatibleSelfHostedProvider({
            ctx,
            providerId: MLX_PROVIDER_ID,
            buildProvider: buildMlxProvider,
          });
        },
      },
      ...buildProviderReplayFamilyHooks({
        family: "openai-compatible",
        dropReasoningFromHistory: false,
      }),
      wizard: {
        setup: {
          choiceId: MLX_PROVIDER_ID,
          choiceLabel: MLX_PROVIDER_LABEL,
          choiceHint: "Apple Silicon MLX server (oMLX, vLLM-MLX, vMLX, mlx-lm)",
          groupId: MLX_PROVIDER_ID,
          groupLabel: MLX_PROVIDER_LABEL,
          groupHint: "Local MLX inference on Apple Silicon",
          methodId: "custom",
        },
        modelPicker: {
          label: "MLX (custom)",
          hint: "Enter MLX server URL + API key + model",
          methodId: "custom",
        },
      },
      buildUnknownModelHint: () =>
        "MLX requires a running OpenAI-compatible MLX server. " +
        'Set MLX_API_KEY (any value works for most local servers) or run "openclaw configure". ' +
        "See: https://docs.openclaw.ai/providers/mlx",
      resolveThinkingProfile,
      wrapStreamFn: wrapMlxProviderStream,
    });
  },
});
