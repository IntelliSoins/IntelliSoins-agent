---
paths:
  - "**/litellm*mcp*"
  - "**/.mcp.json"
  - "**/a2a*"
---

# LiteLLM MCP & Agent Gateway

Unified endpoint for MCP (Model Context Protocol) tools and agent-to-agent (A2A) communication. Works with any LiteLLM-supported LLM backend.

## What is MCP in LiteLLM

Fixed endpoint that proxies tool calls to backend MCP servers. Access controlled by virtual key, team, org. Supports:

- List Tools
- Call Tools
- Prompts
- Resources

## Prerequisites

Enable DB storage for MCP persistence:

```yaml
general_settings:
  store_model_in_db: true
  supported_db_objects: ["mcp"]
```

Or env:

```bash
STORE_MODEL_IN_DB=True
```

## Transport types

| Transport | Use case                           |
| --------- | ---------------------------------- |
| `http`    | Streamable HTTP — direct requests  |
| `sse`     | Server-Sent Events — streaming     |
| `stdio`   | Local process — spawned subprocess |

## Configure MCP servers

```yaml
mcp_servers:
  # HTTP server
  deepwiki_mcp:
    url: "https://mcp.deepwiki.com/mcp"
    transport: "http"

  # SSE server
  zapier_mcp:
    url: "https://actions.zapier.com/mcp/sk-akxxxxx/sse"
    transport: "sse"

  # stdio (npx-spawned)
  circleci_mcp:
    transport: "stdio"
    command: "npx"
    args: ["-y", "@circleci/mcp-server-circleci"]
    env:
      CIRCLECI_TOKEN: "os.environ/CIRCLECI_TOKEN"

  # IntelliSoins PubMed MCP (stdio)
  pubmed_mcp:
    transport: "stdio"
    command: "node"
    args: ["/app/pubmed-mcp-server.js"]
    env:
      DATABASE_URL: "os.environ/DATABASE_URL"
      VOYAGE_API_KEY: "os.environ/VOYAGE_API_KEY"
```

## Authentication types

```yaml
mcp_servers:
  # API key (custom header)
  api_key_example:
    url: "https://my-mcp.com/mcp"
    transport: "http"
    auth_type: "api_key"
    auth_value: os.environ/MY_MCP_API_KEY

  # Bearer token
  bearer_example:
    url: "https://my-mcp.com/mcp"
    transport: "http"
    auth_type: "bearer_token"
    auth_value: os.environ/MY_MCP_TOKEN

  # Basic auth
  basic_example:
    url: "https://my-mcp.com/mcp"
    transport: "http"
    auth_type: "basic"
    auth_value: "dXNlcjpwYXNz" # base64 user:pass

  # OAuth2 (automatic token management)
  oauth2_example:
    url: "https://my-mcp.com/mcp"
    transport: "http"
    auth_type: "oauth2"
    client_id: os.environ/OAUTH_CLIENT_ID
    client_secret: os.environ/OAUTH_CLIENT_SECRET
    scopes: ["tool.read", "tool.write"]
```

## MCP aliases

Shorter names for clients:

```yaml
litellm_settings:
  mcp_aliases:
    "github": "github_mcp_server"
    "zapier": "zapier_mcp_server"
    "pubmed": "pubmed_mcp"
```

Client uses `github` instead of `github_mcp_server`.

## Use MCP in chat completions

```bash
curl '<litellm-proxy>/v1/chat/completions' \
  -H 'Authorization: Bearer $LITELLM_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Search recent PubMed articles on long COVID"}],
    "tools": [{
      "type": "mcp",
      "server_url": "litellm_proxy/mcp/pubmed",
      "require_approval": "never"
    }]
  }'
```

`require_approval`:

- `"never"` — auto-execute
- `"always"` — require user confirmation (via callback)

## Python SDK integration

### List tools

```python
from litellm import experimental_mcp_client

tools = await experimental_mcp_client.load_mcp_tools(
    session=session,
    format="openai"                      # or "anthropic"
)
```

### Call a tool

```python
call_result = await experimental_mcp_client.call_openai_tool(
    session=session,
    openai_tool=openai_tool,
)
```

### Full flow

```python
import asyncio
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from litellm import experimental_mcp_client, acompletion

async def main():
    server_params = StdioServerParameters(command="python", args=["./mcp_server.py"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await experimental_mcp_client.load_mcp_tools(session=session, format="openai")

            response = await acompletion(
                model="anthropic/claude-sonnet-4-6",
                messages=[{"role": "user", "content": "Do X with tools"}],
                tools=tools,
            )

            if response.choices[0].message.tool_calls:
                for tc in response.choices[0].message.tool_calls:
                    result = await experimental_mcp_client.call_openai_tool(session=session, openai_tool=tc)
                    print(result)

asyncio.run(main())
```

## Permission management

Control MCP access by:

- API Key (`/key/generate` with `permissions.mcp_servers: ["github"]`)
- Team
- Organization

```bash
curl 'http://0.0.0.0:4000/key/generate' \
  -H 'Authorization: Bearer $MASTER' \
  -d '{
    "models": ["gpt-4o"],
    "permissions": {
      "allowed_mcp_servers": ["pubmed", "deepwiki"]
    }
  }'
```

Requests using this key can only call those MCP servers via proxy.

## Custom headers forwarded

Client headers can pass through to MCP servers:

```yaml
mcp_servers:
  my_server:
    url: "https://my-mcp.com/mcp"
    transport: "http"
    forward_headers:
      - "x-user-id"
      - "x-session-id"
```

Client:

```bash
curl http://0.0.0.0:4000/v1/chat/completions \
  -H "x-user-id: user-123" \
  -H "x-session-id: session-456" \
  -d '{..., "tools": [{"type": "mcp", "server_url": "litellm_proxy/mcp/my_server"}]}'
```

## A2A Agent Gateway

Agent-to-agent communication via standardized agent cards.

### Register an agent

```bash
curl -X POST 'http://localhost:4000/v1/agents' \
  -H 'Authorization: Bearer sk-1234' \
  -H 'Content-Type: application/json' \
  -d '{
    "agent_name": "pubmed-research-agent",
    "agent_card_params": {
      "name": "pubmed-research-agent",
      "description": "Biomedical literature search and synthesis",
      "url": "http://pubmed-mcp.vps:8080",
      "version": "1.0.0",
      "capabilities": {
        "streaming": true,
        "pushNotifications": false
      },
      "defaultInputModes": ["text"],
      "defaultOutputModes": ["text"],
      "skills": [
        {
          "id": "search",
          "name": "PubMed search",
          "description": "Semantic search across PubMed abstracts"
        }
      ]
    },
    "tpm_limit": 100000,
    "rpm_limit": 100,
    "session_tpm_limit": 50000,
    "session_rpm_limit": 50,
    "litellm_params": {
      "require_trace_id_on_calls_by_agent": true,
      "max_iterations": 25,
      "max_budget_per_session": 5.00
    }
  }'
```

### List registered agents

```bash
curl 'http://localhost:4000/v1/agents' -H 'Authorization: Bearer sk-1234'
```

### Get agent card (A2A discovery)

```bash
curl 'http://localhost:4000/.well-known/agent.json'
```

Returns JSON agent card per A2A spec.

### Invoke agent (A2A JSON-RPC)

```bash
curl -X POST 'http://localhost:4000/v1/agents/<agent_id>/tasks/send' \
  -H 'Authorization: Bearer sk-...' \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "task-001",
    "message": {
      "role": "user",
      "parts": [{"type": "text", "text": "Find 5 systematic reviews on sepsis"}]
    }
  }'
```

### Update agent limits

```bash
curl -X PATCH 'http://localhost:4000/v1/agents/<agent_id>' \
  -H 'Authorization: Bearer sk-1234' \
  -d '{
    "tpm_limit": 200000,
    "rpm_limit": 200
  }'
```

## Agent budgets per session

```bash
curl -X POST 'http://localhost:4000/v1/agents' \
  -d '{
    "agent_name": "masterai",
    "agent_card_params": {...},
    "litellm_params": {
      "max_iterations": 25,
      "max_budget_per_session": 5.00,
      "session_tpm_limit": 50000,
      "session_rpm_limit": 50
    }
  }'
```

Sessions tracked by `session_id` metadata.

## Cost tracking

MCP tool calls and agent invocations tracked in spend logs:

```bash
curl 'http://0.0.0.0:4000/spend/logs?start_date=2026-04-01' \
  -H 'Authorization: Bearer $MASTER'
```

Includes:

- `mcp_server`: which server
- `tool_name`: which tool
- `agent_id`: which agent invoked
- `session_id`: session context

## IntelliSoins integration — carte stratégique

### MCP servers à exposer

```yaml
mcp_servers:
  # Serveur IntelliSoins PubMed (65 outils)
  intellisoins_pubmed:
    transport: "stdio"
    command: "node"
    args: ["/app/dist/lib/agents/mcp/pubmed-mcp-server.js"]
    env:
      DATABASE_URL: "os.environ/DATABASE_URL"
      VOYAGE_API_KEY: "os.environ/VOYAGE_API_KEY"

  # Zotero (via Zapier ou direct)
  zotero:
    url: "https://actions.zapier.com/mcp/sk-xxx/sse"
    transport: "sse"

  # GitHub (via officiel)
  github:
    transport: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "os.environ/GITHUB_TOKEN"
```

### Agents à enregistrer

| Agent name              | Description               | Endpoint             |
| ----------------------- | ------------------------- | -------------------- |
| `intellisoins-pubmed`   | Biomedical RAG + search   | Existing MCP (stdio) |
| `intellisoins-masterai` | Orchestrateur multi-agent | Future HTTP A2A      |
| `website-intellisoins`  | Support marketing         | Future               |

### Virtual key permissions

```bash
curl http://0.0.0.0:4000/key/generate \
  -d '{
    "models": ["claude-sonnet"],
    "permissions": {
      "allowed_mcp_servers": ["intellisoins_pubmed", "zotero"]
    },
    "metadata": {"agent": "pubmed-research"}
  }'
```

Chaque agent IntelliSoins reçoit une key avec accès uniquement à ses MCP servers.

## Features key

- **Provider-agnostic**: fonctionne avec tout LLM backend LiteLLM
- **Access control**: par user/team/key
- **Cost tracking**: utilisation + coût MCP capturés
- **OAuth support**: gestion automatique des tokens
- **Custom headers**: forwarding client → MCP

## Source

docs.litellm.ai/docs/mcp + /docs/agents — scraped 2026-04-14.
