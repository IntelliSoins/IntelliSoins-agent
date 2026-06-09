---
paths:
  - "**/litellm/config*.yaml"
  - "**/litellm-*/config*.yaml"
  - "**/servers.yaml"
  - "**/model_list*"
---

# LiteLLM Providers & Models

100+ providers unified via prefix routing. Format: `<prefix>/<model-id>` in the `model` field.

## Quick reference — major providers

| Provider         | Prefix          | Required env vars                                                                    | Endpoints                               |
| ---------------- | --------------- | ------------------------------------------------------------------------------------ | --------------------------------------- |
| OpenAI           | `openai/`       | `OPENAI_API_KEY`                                                                     | chat, embed, image, audio, mod          |
| Anthropic        | `anthropic/`    | `ANTHROPIC_API_KEY`                                                                  | chat (w/ tools, vision, thinking)       |
| Azure OpenAI     | `azure/`        | `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_API_VERSION`                               | chat, embed, image                      |
| AWS Bedrock      | `bedrock/`      | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION_NAME`                      | chat (Claude, Llama, Titan), embed      |
| Google Vertex AI | `vertex_ai/`    | `GOOGLE_APPLICATION_CREDENTIALS` (path to JSON), `vertex_project`, `vertex_location` | chat (Gemini, Claude via Vertex), embed |
| Google AI Studio | `gemini/`       | `GOOGLE_API_KEY` or `GEMINI_API_KEY`                                                 | chat, embed                             |
| Mistral AI       | `mistral/`      | `MISTRAL_API_KEY`                                                                    | chat, embed                             |
| Cohere           | `cohere/`       | `COHERE_API_KEY`                                                                     | chat, embed, rerank                     |
| Groq             | `groq/`         | `GROQ_API_KEY`                                                                       | chat (low-latency Llama, Mixtral)       |
| Deepseek         | `deepseek/`     | `DEEPSEEK_API_KEY`                                                                   | chat                                    |
| Together AI      | `together_ai/`  | `TOGETHER_API_KEY`                                                                   | chat, embed, image                      |
| Perplexity       | `perplexity/`   | `PERPLEXITY_API_KEY`                                                                 | chat (online search models)             |
| OpenRouter       | `openrouter/`   | `OPENROUTER_API_KEY`                                                                 | chat (aggregator)                       |
| Voyage AI        | `voyage/`       | `VOYAGE_API_KEY`                                                                     | embed, rerank                           |
| xAI              | `xai/`          | `XAI_API_KEY`                                                                        | chat (Grok)                             |
| HuggingFace      | `huggingface/`  | `HUGGINGFACE_API_KEY` + endpoint                                                     | chat, embed                             |
| Databricks       | `databricks/`   | `DATABRICKS_API_KEY`, `DATABRICKS_API_BASE`                                          | chat, embed                             |
| Fireworks AI     | `fireworks_ai/` | `FIREWORKS_AI_API_KEY`                                                               | chat, embed                             |
| Cerebras         | `cerebras/`     | `CEREBRAS_API_KEY`                                                                   | chat (fast Llama)                       |
| SambaNova        | `sambanova/`    | `SAMBANOVA_API_KEY`                                                                  | chat                                    |
| Nvidia NIM       | `nvidia_nim/`   | `NVIDIA_NIM_API_KEY`                                                                 | chat, embed                             |
| Replicate        | `replicate/`    | `REPLICATE_API_KEY`                                                                  | chat, image, video                      |
| AI21             | `ai21/`         | `AI21_API_KEY`                                                                       | chat                                    |

## Self-hosted / local

| Provider                  | Prefix                      | Required config                    | Notes                           |
| ------------------------- | --------------------------- | ---------------------------------- | ------------------------------- |
| Ollama                    | `ollama/`                   | `api_base: http://localhost:11434` | Anthropic API native via v0.14+ |
| Ollama chat               | `ollama_chat/`              | Same                               | Use for chat-tuned models       |
| vLLM                      | `openai/` + `api_base`      | `api_base: http://vllm:8000/v1`    | OpenAI-compat endpoint          |
| LM Studio                 | `lm_studio/`                | `api_base`                         | Desktop dev                     |
| Llamafile                 | `llamafile/`                | `api_base`                         | Single-binary inference         |
| Text-Generation-Inference | `huggingface/` + `api_base` | TGI endpoint                       | HF Inference Server             |

## Audio / speech

| Provider   | Prefix             | Capability          |
| ---------- | ------------------ | ------------------- |
| ElevenLabs | `elevenlabs/`      | TTS + voice cloning |
| Deepgram   | `deepgram/`        | STT                 |
| OpenAI     | `openai/whisper-1` | STT                 |
| OpenAI     | `openai/tts-1`     | TTS                 |

## Image / video

| Provider          | Prefix                                  | Capability                   |
| ----------------- | --------------------------------------- | ---------------------------- |
| OpenAI            | `openai/dall-e-3`, `openai/gpt-image-1` | Image gen                    |
| Stability AI      | `stability/`                            | Image gen (Stable Diffusion) |
| Black Forest Labs | `black_forest_labs/`                    | Image gen (Flux)             |
| Replicate         | `replicate/...`                         | Image + video                |

## Endpoints supported per provider

Not every provider supports every endpoint. Use `GET /v1/models` on the proxy to introspect. Common matrix:

| Endpoint         | OpenAI | Anthropic | Bedrock | Vertex | Ollama  | Voyage | Cohere |
| ---------------- | ------ | --------- | ------- | ------ | ------- | ------ | ------ |
| chat             | ✓      | ✓         | ✓       | ✓      | ✓       | —      | ✓      |
| streaming        | ✓      | ✓         | ✓       | ✓      | ✓       | —      | ✓      |
| tools            | ✓      | ✓         | ✓       | ✓      | partial | —      | ✓      |
| vision           | ✓      | ✓         | ✓       | ✓      | partial | —      | —      |
| embeddings       | ✓      | —         | ✓       | ✓      | ✓       | ✓      | ✓      |
| rerank           | —      | —         | ✓       | —      | —       | ✓      | ✓      |
| image gen        | ✓      | —         | ✓       | ✓      | —       | —      | —      |
| audio transcribe | ✓      | —         | —       | —      | —       | —      | —      |

## Pricing & model_cost lookup

LiteLLM embeds pricing in `litellm.model_cost` (refreshed per release). Access:

```python
from litellm import model_cost
print(model_cost["gpt-4o"])
# {'max_tokens': 4096, 'max_input_tokens': 128000,
#  'input_cost_per_token': 0.0000025, 'output_cost_per_token': 0.00001, ...}
```

Latest table: [models.litellm.ai](https://models.litellm.ai) or file `litellm/model_prices_and_context_window_backup.json` in repo.

Custom pricing for providers/models not in DB:

```yaml
model_list:
  - model_name: custom-model
    litellm_params:
      model: openai/custom
      api_base: https://my-endpoint.com
      input_cost_per_token: 0.000001
      output_cost_per_token: 0.000003
```

## Full provider list (100+)

AI21, Aleph Alpha, Amazon Nova, Anthropic, Anyscale, Aporia, Azure AI, Azure OpenAI, Baseten, Bedrock, Bytez, Cerebras, Clarifai, Cohere, Databricks, DataRobot, Deepgram, DeepInfra, Deepseek, ElevenLabs, Fireworks AI, Gemini, GitHub Models, GradientAI, Groq, Heroku, HuggingFace, Jina AI, Lambda AI, Lemur, Lepton, LM Studio, Llamafile, Meta Llama, MiniMax, Mistral, Moonshot, NLP Cloud, Novita AI, Nscale, Nvidia NIM, Ollama, OpenAI, OpenRouter, Oracle OCI, Perplexity, PetalsRuntime, Predibase, Replicate, Sagemaker, SambaNova, Sarvam.ai, SAP GenAI Hub, Scaleway, Snowflake, Stability AI, Together AI, Triton, VertexAI, vLLM, Voyage AI, Watsonx, xAI, …

Complete docs: [docs.litellm.ai/docs/providers](https://docs.litellm.ai/docs/providers).

## IntelliSoins providers actuels

Déjà utilisés dans le stack — à intégrer dès le déploiement LiteLLM:

| Provider  | Usage IntelliSoins               | Prefix LiteLLM                                                                                    |
| --------- | -------------------------------- | ------------------------------------------------------------------------------------------------- |
| Anthropic | Opus/Sonnet/Haiku pour agent SDK | `anthropic/claude-opus-4-6`, `anthropic/claude-sonnet-4-6`, `anthropic/claude-haiku-4-5-20251001` |
| Voyage AI | Embeddings 1024D pgvector        | `voyage/voyage-3`                                                                                 |
| Ollama    | LLMs locaux VPS/Mac              | `ollama/<model>` via `api_base: http://ollama:11434`                                              |
| OpenAI    | Fallback, audio Whisper          | `openai/gpt-4o`, `openai/whisper-1`                                                               |

## Troubleshooting

| Erreur                                       | Cause                             | Fix                                                                |
| -------------------------------------------- | --------------------------------- | ------------------------------------------------------------------ |
| `BadRequestError: LLM Provider NOT provided` | Préfixe manquant                  | Utiliser `provider/model` format                                   |
| `AuthenticationError`                        | Env var manquant                  | Vérifier variable exacte (`ANTHROPIC_API_KEY` vs `CLAUDE_API_KEY`) |
| `Unsupported parameter X`                    | Provider ne supporte pas le champ | Activer `drop_params: true` dans `litellm_settings`                |
| Modèle absent de `/v1/models`                | Pas dans `model_list`             | Ajouter au config.yaml + restart                                   |

## Source

docs.litellm.ai/docs/providers — scraped 2026-04-14.
Pricing: models.litellm.ai / model_prices_and_context_window_backup.json.
