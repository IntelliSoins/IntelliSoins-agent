---
paths:
  - "**/claude-agent-sdk*"
  - "**/claude*max*litellm*"
  - "**/ANTHROPIC_BASE_URL*"
  - "**/claude_agent*.py"
---

# Claude Agent SDK via LiteLLM Proxy

The Anthropic **Claude Agent SDK** (Python + TypeScript) speaks the Anthropic Messages API. Set `ANTHROPIC_BASE_URL` to a LiteLLM Proxy and the SDK routes its agent loop through any provider behind the proxy (Bedrock, Vertex, Azure, OpenAI, local MLX, Ollama). LiteLLM translates Anthropic Messages ↔ provider format both ways, so tool calls, streaming, and structured output keep working.

## Common pattern (Python + TypeScript)

Both SDKs use the same two environment variables:

| Env var              | Value                                                      | Purpose                                                               |
| -------------------- | ---------------------------------------------------------- | --------------------------------------------------------------------- |
| `ANTHROPIC_BASE_URL` | `http://localhost:4000` (or `https://llm.intellisoins.ca`) | Redirect SDK away from `api.anthropic.com` to the proxy               |
| `ANTHROPIC_API_KEY`  | LiteLLM virtual key (`sk-...`) or master key               | Proxy gateway auth — LiteLLM checks budget/rate limits, not Anthropic |

The model name passed to the SDK must match a `model_name` in the proxy `model_list` (case-sensitive).

## LiteLLM config (minimal)

Define one or more models in `config.yaml`:

```yaml
model_list:
  - model_name: bedrock-claude-sonnet-4.5
    litellm_params:
      model: "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
      aws_region_name: "us-east-1"
```

Full config reference: skill `litellm-config-yaml`. Provider prefix table (`bedrock/`, `vertex_ai/`, `azure/`, `openai/`, `ollama/`, …): skill `litellm-providers-models`.

## Python: `claude-agent-sdk`

### Install

```bash
uv add claude-agent-sdk
# or
pip install claude-agent-sdk
```

### Hello-world (async streaming)

```python
import asyncio
import os
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

os.environ["ANTHROPIC_BASE_URL"] = "http://localhost:4000"
os.environ["ANTHROPIC_API_KEY"] = "sk-1234"

options = ClaudeAgentOptions(
    system_prompt="You are a helpful AI assistant.",
    model="bedrock-claude-sonnet-4",
    max_turns=20,
)

async def main():
    async with ClaudeSDKClient(options=options) as client:
        await client.query("What is LiteLLM?")
        async for msg in client.receive_response():
            if hasattr(msg, "content"):
                for content_block in msg.content:
                    if hasattr(content_block, "text"):
                        print(content_block.text, end="", flush=True)

asyncio.run(main())
```

### Key `ClaudeAgentOptions` fields

| Field             | Type | Notes                                                 |
| ----------------- | ---- | ----------------------------------------------------- |
| `model`           | str  | **Must match** `model_name` in LiteLLM `model_list`   |
| `system_prompt`   | str  | Custom system prompt (overrides Claude Code preset)   |
| `max_turns`       | int  | Cap on agentic tool-use rounds                        |
| `permission_mode` | str  | `default`, `acceptEdits`, `bypassPermissions`, `plan` |
| `cwd`             | str  | Working directory for filesystem tools                |
| `mcp_servers`     | dict | MCP servers to expose to the agent                    |

Source: tutorial `docs.litellm.ai/docs/tutorials/claude_agent_sdk`.

## TypeScript: `@anthropic-ai/claude-agent-sdk`

### Install

```bash
npm install @anthropic-ai/claude-agent-sdk
```

The package ships native CLI binaries as optional deps (`@anthropic-ai/claude-agent-sdk-darwin-arm64`, etc.).

### Hello-world (async iterator)

```typescript
import { query } from "@anthropic-ai/claude-agent-sdk";

process.env.ANTHROPIC_BASE_URL = "http://localhost:4000";
process.env.ANTHROPIC_API_KEY = "sk-1234";

for await (const message of query({
  prompt: "What files are here?",
  options: {
    model: "bedrock-claude-sonnet-4",
    maxTurns: 5,
    systemPrompt: "You are a helpful AI assistant.",
  },
})) {
  console.log(message);
}
```

The `model` is passed inside the `options` object — same idea as `ClaudeAgentOptions.model` in Python.

### Pre-warming with `startup()`

Spawn the CLI subprocess at app boot so the first user query resolves without spawn/init latency:

```typescript
import { startup } from "@anthropic-ai/claude-agent-sdk";

const warm = await startup({
  options: {
    model: "bedrock-claude-sonnet-4",
    maxTurns: 3,
  },
});

for await (const message of warm.query("What files are here?")) {
  console.log(message);
}
```

### Key `Options` fields

| Field            | Type                                                                | Notes                                               |
| ---------------- | ------------------------------------------------------------------- | --------------------------------------------------- |
| `model`          | string                                                              | **Must match** `model_name` in LiteLLM `model_list` |
| `maxTurns`       | number                                                              | Cap on agentic tool-use rounds                      |
| `systemPrompt`   | string \| `{ type: "preset"; preset: "claude_code" }`               | Custom or preset system prompt                      |
| `permissionMode` | `'default'` \| `'acceptEdits'` \| `'bypassPermissions'` \| `'plan'` | Permission gate                                     |
| `cwd`            | string                                                              | Working directory                                   |
| `debug`          | boolean                                                             | Verbose logging                                     |

Source: `code.claude.com/docs/en/agent-sdk/typescript`.

## Caveats

### MCP tool search disabled with custom `ANTHROPIC_BASE_URL`

Per Anthropic env-var docs (`code.claude.com/docs/en/env-vars`):

> `ANTHROPIC_BASE_URL` — Override the API endpoint to route requests through a proxy or gateway. When set to a non-first-party host, MCP tool search is disabled by default. Set `ENABLE_TOOL_SEARCH=true` if your proxy forwards `tool_reference` blocks.

LiteLLM Proxy forwards `tool_reference` blocks transparently for Anthropic upstreams. If your agent loses tool-search behavior the moment you point at the proxy:

```bash
export ENABLE_TOOL_SEARCH=true
```

For non-Anthropic upstreams (Bedrock, Vertex, OpenAI, local MLX), `tool_reference` blocks may be dropped by the provider regardless — verify with a direct curl against the proxy before enabling.

### Other gotchas

1. `model` in `ClaudeAgentOptions` / TS `options` must match `model_name` exactly (case-sensitive). LiteLLM virtual-key `aliases` can map external → internal names.
2. Provider feature parity is not guaranteed (extended thinking, vision, tool calls). Set `drop_params: true` in `litellm_settings` to silently drop unsupported fields rather than 400.
3. Virtual key budgets/rate limits apply to every SDK request — long agent loops can burn through `tpm_limit` quickly. See skill `litellm-budgets-spend`.
4. Streaming works through the proxy as long as the proxy itself doesn't buffer (Traefik/Nginx may need `X-Accel-Buffering: no`).

## IntelliSoins integration

Sur le gateway local `:8092` (cf. auto-mémoire `~/.claude/projects/-Users-michaelahern-ai-servers/memory/project_litellm_gateway.md`): le master key vit dans Keychain, 57+ modèles déjà configurés. Pointer le SDK vers `ANTHROPIC_BASE_URL=http://localhost:8092` avec une virtual key par agent (génération: skill `litellm-authentication`). Pour les routes Loi 25, choisir un `model_name` qui mappe vers un modèle local MLX (`omlx-*`, `vllm-mlx-*`) plutôt que Bedrock US.

## Cross-reference

- Deploy proxy (Docker, Traefik, VPS): skill `litellm-proxy-setup`
- Generate virtual keys for the SDK: skill `litellm-authentication`
- `config.yaml` full reference: skill `litellm-config-yaml`
- Provider prefixes (Bedrock, Vertex, Azure, …): skill `litellm-providers-models`
- Routing/fallbacks across providers: skill `litellm-routing-fallbacks`
- Budgets/rate limits per virtual key: skill `litellm-budgets-spend`

## Examples

- **BerriAI cookbook** — `github.com/BerriAI/litellm/tree/main/cookbook/anthropic_agent_sdk` : interactive CLI agent Python avec streaming temps réel, switch de modèle dynamique, fetch des modèles disponibles via le proxy. Bon point de départ pour reproduire le flow `ANTHROPIC_BASE_URL` côté client.

## Source

- `docs.litellm.ai/docs/tutorials/claude_agent_sdk` — scraped 2026-05-05
- `code.claude.com/docs/en/agent-sdk/typescript` — scraped 2026-05-05
- `code.claude.com/docs/en/env-vars` — scraped 2026-05-05
- `github.com/BerriAI/litellm/tree/main/cookbook/anthropic_agent_sdk` — referenced 2026-05-09
