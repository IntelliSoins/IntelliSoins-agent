---
paths:
  - "**/litellm*guardrail*"
  - "**/presidio*"
  - "**/lakera*"
---

# LiteLLM Guardrails & Policies

Content safety layer — intercepts requests before/during/after LLM call. Critical for medical/compliance (Loi 25, HIPAA, RGPD).

## Supported guardrail providers

| Provider                   | Purpose                                  | Type                  |
| -------------------------- | ---------------------------------------- | --------------------- |
| **Presidio**               | PII detection + masking (self-host)      | Open-source           |
| **AWS Bedrock Guardrails** | Managed content policy (AWS)             | Managed               |
| **Lakera AI**              | Prompt injection, toxicity               | Managed               |
| **Aporia**                 | Custom policies, observability           | Managed               |
| **AIM (Guardrails AI)**    | Framework-based                          | Open-source + managed |
| **Pillar Security**        | Custom API integration                   | Managed               |
| **OpenAI Moderation**      | Built-in `omni-moderation-latest`        | Managed               |
| **LiteLLM Content Filter** | Built-in keyword/regex                   | Free                  |
| **Custom**                 | Python class implementing hook interface | DIY                   |

## Modes (when guardrail runs)

| Mode           | When                              | Blocks call?                            |
| -------------- | --------------------------------- | --------------------------------------- |
| `pre_call`     | Before LLM call, on input         | Yes — replaces or rejects input         |
| `during_call`  | Parallel with LLM call            | Response waits until guardrail finishes |
| `post_call`    | After LLM call, on input + output | Yes — can mask/reject output            |
| `logging_only` | Parallel, non-blocking            | No — observability only                 |

Multi-mode:

```yaml
mode: [pre_call, post_call]
```

## Config structure

```yaml
guardrails:
  - guardrail_name: "presidio-pii" # unique ID
    litellm_params:
      guardrail: presidio # provider
      mode: "pre_call"
      default_on: false # opt-in via key/request
      pii_entities_config:
        CREDIT_CARD: "MASK"
        EMAIL_ADDRESS: "MASK"
        PHONE_NUMBER: "MASK"
        PERSON: "BLOCK"
      presidio_language: "en"
      presidio_analyzer_api_base: "http://presidio-analyzer:5002"
      presidio_anonymizer_api_base: "http://presidio-anonymizer:5001"

  - guardrail_name: "bedrock-guard-production"
    litellm_params:
      guardrail: bedrock
      mode: "post_call"
      guardrailIdentifier: "bedrock-guard-1"
      guardrailVersion: "DRAFT"
      aws_region_name: us-east-1

  - guardrail_name: "lakera-prompt-injection"
    litellm_params:
      guardrail: lakera
      mode: "pre_call"
      api_key: os.environ/LAKERA_API_KEY
      category_thresholds:
        prompt_injection: 0.5
        jailbreak: 0.3
```

## Presidio — PII

Two modes supported:

- `MASK`: replace entity with placeholder (`<EMAIL>`)
- `BLOCK`: reject the call with 400

Entities (subset of 50+):
`CREDIT_CARD`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `PERSON`, `LOCATION`, `IP_ADDRESS`, `DATE_TIME`, `MEDICAL_LICENSE`, `URL`, `US_SSN`, `IBAN_CODE`, `NRP`, `CA_SIN` (Canadian SIN), `US_PASSPORT`.

```yaml
guardrails:
  - guardrail_name: "medical-pii"
    litellm_params:
      guardrail: presidio
      mode: [pre_call, post_call]
      default_on: true
      pii_entities_config:
        PERSON: "MASK"
        PHONE_NUMBER: "MASK"
        EMAIL_ADDRESS: "MASK"
        CA_SIN: "BLOCK"
        MEDICAL_LICENSE: "MASK"
      presidio_language: "fr" # or "en"
```

IntelliSoins: déjà deploye via stack (voir `~/.claude/rules/presidio-anonymization.md`).

## AWS Bedrock Guardrails

Managed content policy (toxicity, prompt attacks, denied topics):

```yaml
guardrails:
  - guardrail_name: "bedrock-medical-policy"
    litellm_params:
      guardrail: bedrock
      mode: "post_call"
      guardrailIdentifier: "abc-xyz-123"
      guardrailVersion: "DRAFT"
      aws_region_name: us-east-1
      aws_access_key_id: os.environ/AWS_ACCESS_KEY_ID
      aws_secret_access_key: os.environ/AWS_SECRET_ACCESS_KEY
```

## Lakera — prompt injection / jailbreak

```yaml
guardrails:
  - guardrail_name: "lakera-input"
    litellm_params:
      guardrail: lakera
      mode: "pre_call"
      api_key: os.environ/LAKERA_API_KEY
      category_thresholds:
        prompt_injection: 0.5
        jailbreak: 0.3
        pii: 0.8
```

## OpenAI Moderation

```yaml
guardrails:
  - guardrail_name: "openai-mod"
    litellm_params:
      guardrail: openai_moderation
      mode: "pre_call"
      api_key: os.environ/OPENAI_API_KEY
```

Blocks on categories: `hate`, `harassment`, `self-harm`, `sexual`, `violence`.

## Guardrails AI (framework)

```yaml
guardrails:
  - guardrail_name: "guardrails-ai-custom"
    litellm_params:
      guardrail: guardrails_ai
      mode: "post_call"
      guard_name: "medical_advice_validator"
      api_base: "http://guardrails-ai:8000"
```

## Apply per-key

```bash
curl 'http://0.0.0.0:4000/key/generate' \
  -H 'Authorization: Bearer $MASTER' \
  -d '{
    "guardrails": ["presidio-pii", "lakera-input"],
    "models": ["claude-sonnet"]
  }'
```

All requests with this key run those guardrails.

## Apply per-request

```bash
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-..." \
  -d '{
    "model": "gpt-3.5-turbo",
    "guardrails": ["presidio-pii"],
    "messages": [...]
  }'
```

## Default-on (Enterprise)

Force guardrail on all requests without client opt-in:

```yaml
guardrails:
  - guardrail_name: "presidio-mandatory"
    litellm_params:
      guardrail: presidio
      mode: "pre_call"
      default_on: true # always runs
```

## Custom guardrail (Python)

```python
# custom_guardrails.py
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm._logging import verbose_logger

class ForbiddenKeywordsGuard(CustomGuardrail):
    async def async_pre_call_hook(
        self, user_api_key_dict, cache, data, call_type
    ):
        forbidden = ["secret_project_alpha", "confidential_dossier"]
        messages = data.get("messages", [])
        for msg in messages:
            for word in forbidden:
                if word in str(msg.get("content", "")):
                    raise Exception(f"Forbidden keyword: {word}")
        return data

    async def async_post_call_hook(
        self, data, user_api_key_dict, response
    ):
        return response
```

```yaml
litellm_settings:
  callbacks: custom_guardrails.ForbiddenKeywordsGuard

guardrails:
  - guardrail_name: "forbidden-keywords"
    litellm_params:
      guardrail: custom_guardrails.ForbiddenKeywordsGuard
      mode: "pre_call"
```

## Dynamic parameters (Enterprise)

Pass runtime config via `extra_body`:

```bash
curl http://localhost:4000/v1/chat/completions \
  -d '{
    "model": "gpt-4o",
    "messages": [...],
    "guardrails": ["presidio-pii"],
    "guardrail_config": {
      "presidio_language": "fr",
      "pii_entities_config": {"PERSON": "BLOCK"}
    }
  }'
```

## Tag-based modes (Enterprise)

Different modes per client type:

```yaml
guardrails:
  - guardrail_name: "context-aware"
    litellm_params:
      guardrail: presidio
      mode:
        default: "logging_only"
        tags:
          production: "pre_call"
          public-api: "post_call"
```

Tag injected via `x-litellm-tags: production` header.

## Model-level (Enterprise)

Attach guardrail to specific model:

```yaml
model_list:
  - model_name: medical-advisor
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      guardrails: ["presidio-pii", "bedrock-medical-policy"]
```

## Logging only (observability)

Track detections without blocking — useful for rollout:

```yaml
guardrails:
  - guardrail_name: "presidio-shadow"
    litellm_params:
      guardrail: presidio
      mode: "logging_only"
      default_on: true
```

Review logs (skill `litellm-logging-metrics`) before enforcing.

## Order of execution

If multiple guardrails defined:

1. `pre_call` guardrails run sequentially (fail-fast)
2. LLM call executes
3. `during_call` runs in parallel (response awaits completion)
4. `post_call` runs sequentially on input + output
5. `logging_only` runs async (non-blocking)

## IntelliSoins usage

### Production medical RAG

```yaml
guardrails:
  - guardrail_name: "presidio-patient-pii"
    litellm_params:
      guardrail: presidio
      mode: [pre_call, post_call]
      default_on: true
      pii_entities_config:
        PERSON: "MASK"
        CA_SIN: "BLOCK" # Quebec health IDs
        MEDICAL_LICENSE: "MASK"
        PHONE_NUMBER: "MASK"
        EMAIL_ADDRESS: "MASK"
        DATE_TIME: "MASK" # masks DOB
      presidio_language: "fr"
```

### API publique (usagers externes)

```yaml
- guardrail_name: "lakera-public"
  litellm_params:
    guardrail: lakera
    mode: "pre_call"
    category_thresholds:
      prompt_injection: 0.3 # strict
      jailbreak: 0.3
```

### Output validation (réponses cliniques)

```yaml
- guardrail_name: "medical-factcheck"
  litellm_params:
    guardrail: guardrails_ai
    mode: "post_call"
    guard_name: "clinical_claims_validator"
```

## Compliance cross-ref

- Loi 25 (Québec) + RGPD → Presidio obligatoire
- HIPAA (si patients US) → Bedrock Guardrails + Presidio
- TGV MSSS → voir `~/.claude/rules/tgv-certification.md`

## Source

docs.litellm.ai/docs/proxy/guardrails/quick_start + individual guardrails — scraped 2026-04-14.
