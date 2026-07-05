---
summary: "Run OpenClaw with Apple Silicon MLX servers (oMLX, vLLM-MLX, vMLX, mlx-lm)"
read_when:
  - You want native OpenClaw support for local MLX inference on macOS
  - You run oMLX, vLLM-MLX, vMLX, mlx-openai-server, mlxcel, or mlx-lm
title: "MLX"
---

Apple Silicon MLX servers expose an OpenAI-compatible `/v1` API. OpenClaw connects through the bundled `mlx` provider using `openai-completions`, auto-discovery, tool-call compat, optional prompt-cache hints, and Qwen/Nemotron thinking wrappers.

| Property                  | Value                                                                                         |
| ------------------------- | --------------------------------------------------------------------------------------------- |
| Provider id               | `mlx`                                                                                         |
| Legacy hook alias         | `omlx-local` (compat routing only)                                                            |
| Plugin                    | bundled, `enabledByDefault: true`                                                             |
| Auth env var              | `MLX_API_KEY` (any non-empty value if the server has no auth)                                 |
| Backend selector          | `MLX_BACKEND` (`omlx`, `vllm-mlx`, `vmlx`, `mlx-lm`, `mlx-openai-server`, `mlxcel`, `custom`) |
| Onboarding flag           | `--auth-choice mlx`                                                                           |
| API                       | OpenAI-compatible (`openai-completions`)                                                      |
| Default base URL          | `http://127.0.0.1:8000/v1` (backend-specific defaults apply)                                  |
| Default model placeholder | `mlx/mlx-community/Qwen3-8B-4bit`                                                             |
| Streaming usage           | Yes (`supportsStreamingUsage: true`)                                                          |
| Pricing                   | Marked external-free (`modelPricing.external: false`)                                         |

Supported backends include:

| Backend             | Typical server                                                     | Default base URL           |
| ------------------- | ------------------------------------------------------------------ | -------------------------- |
| `omlx`              | [oMLX](https://github.com/jundot/omlx)                             | `http://127.0.0.1:8000/v1` |
| `vllm-mlx`          | [vLLM-MLX](https://github.com/waybarrios/vllm-mlx)                 | `http://127.0.0.1:8000/v1` |
| `vmlx`              | [vMLX](https://github.com/jjang-ai/vmlx)                           | `http://127.0.0.1:8000/v1` |
| `mlx-lm`            | `mlx_lm.server`                                                    | `http://127.0.0.1:8080/v1` |
| `mlx-openai-server` | [mlx-openai-server](https://github.com/cubist38/mlx-openai-server) | `http://127.0.0.1:8000/v1` |
| `mlxcel`            | mlxcel-server                                                      | `http://127.0.0.1:8097/v1` |
| `custom`            | Any OpenAI-compatible MLX endpoint                                 | Uses configured `baseUrl`  |

Set `MLX_BACKEND` before onboarding or discovery when your server matches one of the presets above. Override `models.providers.mlx.baseUrl` whenever your server listens on a non-default port.

## Getting started

<Steps>
  <Step title="Start an MLX server">
    Launch one of the supported MLX backends with an OpenAI-compatible `/v1`
    surface. Confirm the models endpoint responds, for example:

    ```bash
    curl http://127.0.0.1:8000/v1/models
    ```

  </Step>
  <Step title="Select the backend preset (optional)">
    ```bash
    export MLX_BACKEND="omlx"
    export MLX_API_KEY="mlx-local"
    ```

    oMLX may require a real API key from its settings file. Use that value for
    `MLX_API_KEY` or `OMLX_API_KEY`.

  </Step>
  <Step title="Run onboarding or set a model directly">
    ```bash
    openclaw onboard
    ```

    Or configure the model manually:

    ```json5
    {
      agents: {
        defaults: {
          model: { primary: "mlx/mlx-community/Qwen3-8B-4bit" },
        },
      },
    }
    ```

  </Step>
  <Step title="Verify discovery">
    ```bash
    openclaw models list --provider mlx
    ```
  </Step>
</Steps>

## Model discovery (implicit provider)

When `MLX_API_KEY` is set (or an auth profile exists) and you **do not** define
`models.providers.mlx`, OpenClaw queries the backend default `/v1/models`
endpoint and converts returned IDs into catalog entries.

Discovered MLX models get OpenClaw-native compat defaults:

- `compat.supportedParameters: ["tools", "tool_choice"]`
- `compat.supportsPromptCacheKey: true` for tiered-cache backends (`omlx`, `vllm-mlx`, `vmlx`, `mlx-openai-server`, `mlxcel`)
- Vision `input: ["text", "image"]` for common VLM ids (`Qwen2-VL`, `Qwen3.5`, `LLaVA`, `Gemma 4`, …)
- Qwen thinking transport hints via `compat.thinkingFormat: "qwen-chat-template"`

<Note>
If you set `models.providers.mlx` explicitly, OpenClaw uses your declared models
by default. Add `"mlx/*": {}` to `agents.defaults.models` when you want OpenClaw
to query that configured provider's `/models` endpoint and include all
advertised MLX models.
</Note>

## Explicit configuration (manual models)

Use explicit config when:

- Your MLX server runs on a custom host or port.
- You want to pin `contextWindow`, `maxTokens`, or vision input manually.
- You need `localService` on-demand startup. See [Local model services](/gateway/local-model-services).

```json5
{
  agents: {
    defaults: {
      model: { primary: "mlx/mlx-community/Qwen3-8B-4bit" },
    },
  },
  models: {
    mode: "merge",
    providers: {
      mlx: {
        baseUrl: "http://127.0.0.1:8010/v1",
        apiKey: "mlx-local",
        api: "openai-completions",
        timeoutSeconds: 300,
        models: [
          {
            id: "mlx-community/Qwen3-8B-4bit",
            name: "Qwen3 8B MLX",
            reasoning: true,
            input: ["text"],
            cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
            contextWindow: 131072,
            maxTokens: 8192,
            compat: {
              supportedParameters: ["tools", "tool_choice"],
              supportsPromptCacheKey: true,
              thinkingFormat: "qwen-chat-template",
            },
          },
        ],
      },
    },
  },
}
```

Catalog ids stay provider-local. Do **not** prefix them with `mlx/` inside
`models.providers.mlx.models[].id`. Select the model as
`mlx/mlx-community/Qwen3-8B-4bit` in agent config.

## Vision models (VLM)

For multimodal MLX backends such as vLLM-MLX or oMLX serving Qwen-VL / Qwen3.5
vision builds, OpenClaw auto-detects common vision model ids during discovery.
If your endpoint uses a custom name, set `input: ["text", "image"]` explicitly.

## Prompt cache and agentic workloads

Tiered KV backends (oMLX, vLLM-MLX, vMLX) benefit from OpenClaw prompt-cache
retention when models declare `compat.supportsPromptCacheKey: true`. You can
still set `agents.defaults.models.<ref>.params.cacheRetention` explicitly.

## oMLX one-click setup

oMLX can launch OpenClaw with pre-wired provider settings:

```bash
omlx launch openclaw
```

Manual OpenClaw config remains compatible. Legacy configs that used the internal
hook alias `omlx-local` continue to route through the bundled `mlx` provider.

## Related docs

- [Local models](/gateway/local-models)
- [Local model services](/gateway/local-model-services)
- [LM Studio](/providers/lmstudio)
- [vLLM](/providers/vllm)
