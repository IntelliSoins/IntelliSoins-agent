# OpenClaw Provider Catalog

## Provider Families

| Family      | Examples                                                                    | Auth                             |
| ----------- | --------------------------------------------------------------------------- | -------------------------------- |
| Cloud       | Anthropic, OpenAI, Google Gemini, OpenRouter, Together, NVIDIA, AWS Bedrock | API key or IAM                   |
| Self-hosted | Ollama, Hugging Face, OpenAI-compatible endpoints                           | local discovery or manual config |
| Regional    | Qwen, Kimi, BytePlus/Doubao, Qianfan, Xiaomi                                | API key                          |
| OAuth       | GitHub Copilot, Gemini CLI, Qwen Portal, Minimax Portal                     | OAuth token                      |

## Key Provider Files

| File                                              | Role                          |
| ------------------------------------------------- | ----------------------------- |
| `src/agents/models-config.providers.ts`           | Central registry              |
| `src/agents/models-config.providers.static.ts`    | Static provider config        |
| `src/agents/models-config.providers.discovery.ts` | Ollama/HF discovery           |
| `src/agents/failover-error.ts`                    | Failover error classification |

## OpenAI-Compatible Template

```json
{
  "providers": {
    "local-provider": {
      "type": "openai-compatible",
      "baseUrl": "http://localhost:PORT/v1",
      "model": "model-name",
      "contextWindow": 131072,
      "reasoning": false,
      "apiKey": "optional-key"
    }
  }
}
```
