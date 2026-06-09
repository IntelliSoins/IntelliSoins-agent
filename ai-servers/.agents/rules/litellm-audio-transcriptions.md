---
paths:
  - "**/litellm*transcrib*"
  - "**/stt*"
  - "**/transcribe*"
  - "**/audio_transcription*"
---

# LiteLLM `/audio/transcriptions` — Speech-to-Text

Endpoint OpenAI-compatible pour transcrire un fichier audio. Disponible côté SDK Python (`litellm.transcription`) et Proxy (`POST /v1/audio/transcriptions`). Support natif fallbacks, cost tracking, logging, guardrails sur le texte transcrit.

## Matrice des features

| Feature           | Status | Notes                                                          |
| ----------------- | ------ | -------------------------------------------------------------- |
| Cost tracking     | ✓      | Tous providers supportés                                       |
| Logging callbacks | ✓      | Langfuse, OTel, Datadog, etc. (via `litellm-logging-metrics`)  |
| End-user tracking | ✓      | Header `x-litellm-end-user-id`                                 |
| Fallbacks         | ✓      | Par requête (`extra_body`) ou via `litellm_settings.fallbacks` |
| Loadbalancing     | ✓      | Plusieurs deployments avec même `model_name`                   |
| Guardrails        | ✓      | Sur output transcribed text (non-streaming uniquement)         |

## Providers supportés

`openai`, `azure`, `vertex_ai`, `gemini`, `deepgram`, `groq`, `fireworks_ai`, `ovhcloud`, `mistral` (Voxtral).

## Stack locale Michael — modèle déjà configuré

Le proxy local (`http://127.0.0.1:8092/v1`) expose déjà :

```yaml
# ~/ai-servers/litellm-proxy/config.yaml:206-210
- model_name: whisper-stt
  litellm_params:
    model: openai/whisper-large-v3-turbo
    api_base: http://127.0.0.1:2022/v1 # backend MLX local (vMLX/parakeet-mlx)
    api_key: dummy
```

> **Backend DOWN par défaut.** Avant de transcrire : `aictl start whisper-stt`.
> Cf. `~/.claude/rules/local-ai-stack.md` et skill `intellisoins-infrastructure:local-ai-servers`.

Pour ajouter cost tracking explicite et activer le routing `/audio/transcriptions`, déclarer le mode :

```yaml
- model_name: whisper-stt
  litellm_params:
    model: openai/whisper-large-v3-turbo
    api_base: http://127.0.0.1:2022/v1
    api_key: dummy
  model_info:
    mode: audio_transcription # CRITIQUE — active la route audio dans le router
```

Sans `mode: audio_transcription` dans `model_info`, le proxy peut tenter d'envoyer la requête sur la route `chat/completions` selon le call type → 4xx.

## Quick Start

### SDK Python (in-process)

```python
from litellm import transcription

with open("/path/to/audio.mp3", "rb") as f:
    response = transcription(
        model="openai/whisper-large-v3-turbo",
        file=f,
        api_base="http://127.0.0.1:2022/v1",
        api_key="dummy",
    )

print(response.text)
```

### Via Proxy local (recommandé — tracking + fallbacks)

Auth via Keychain (jamais hardcoder la master key). Cf. `local-ai-stack.md`.

```python
import subprocess
from openai import OpenAI

master = subprocess.check_output([
    "security", "find-generic-password",
    "-a", "michaelahern", "-s", "litellm-master-key", "-w"
]).decode().strip()

client = OpenAI(base_url="http://127.0.0.1:8092/v1", api_key=master)

with open("/path/to/audio.mp3", "rb") as f:
    transcript = client.audio.transcriptions.create(
        model="whisper-stt",
        file=f,
    )

print(transcript.text)
```

### Curl (test rapide)

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

curl -X POST 'http://127.0.0.1:8092/v1/audio/transcriptions' \
  -H "Authorization: Bearer $MASTER" \
  --form 'file=@"/Users/michaelahern/audio/sample.mp3"' \
  --form 'model="whisper-stt"'
```

> Format : `multipart/form-data`. Le champ `file` doit être un binaire (pas un path JSON). Erreur typique : `Content-Type: application/json` + `file: "/path/..."` → 400.

## Fallbacks

Deux niveaux : par-requête (override ad-hoc) et global (config proxy).

### Fallback par requête — Python SDK OpenAI

```python
with open("audio.mp3", "rb") as f:
    transcript = client.audio.transcriptions.create(
        model="whisper-stt",                           # primary local
        file=f,
        extra_body={
            "fallbacks": ["groq/whisper-large-v3", "openai/whisper-1"]
        }
    )
```

Si `whisper-stt` retourne 5xx ou timeout (backend MLX DOWN, OOM), LiteLLM retry sur `groq/whisper-large-v3` puis `openai/whisper-1`. Cost tracking attribué au modèle qui a effectivement répondu.

### Fallback par requête — curl

```bash
curl -X POST 'http://127.0.0.1:8092/v1/audio/transcriptions' \
  -H "Authorization: Bearer $MASTER" \
  --form 'file=@"audio.mp3"' \
  --form 'model="whisper-stt"' \
  --form 'fallbacks[]="groq/whisper-large-v3"' \
  --form 'fallbacks[]="openai/whisper-1"'
```

### Fallback global — config proxy

```yaml
# config.yaml
litellm_settings:
  fallbacks:
    - whisper-stt: ["groq/whisper-large-v3", "openai/whisper-1"]
```

Cf. skill `litellm-routing-fallbacks` pour fallbacks `context_window`, `content_policy`, retries, cooldowns.

### Tester la chaîne sans casser le primary

`mock_testing_fallbacks=true` force un échec simulé du primary → la chaîne s'exécute. Utile en CI.

```python
transcript = client.audio.transcriptions.create(
    model="whisper-stt",
    file=open("audio.mp3", "rb"),
    extra_body={
        "fallbacks": ["openai/whisper-1"],
        "mock_testing_fallbacks": True,
    }
)
# Le primary "whisper-stt" est mock-failed → la transcription vient de openai/whisper-1
```

## Config provider-spécifique

### Azure

```yaml
- model_name: whisper
  litellm_params:
    model: azure/azure-whisper
    api_version: 2024-02-15-preview
    api_base: os.environ/AZURE_EUROPE_API_BASE
    api_key: os.environ/AZURE_EUROPE_API_KEY
  model_info:
    mode: audio_transcription
```

### Groq (whisper-large-v3, ultra-rapide)

```yaml
- model_name: groq-whisper
  litellm_params:
    model: groq/whisper-large-v3
    api_key: os.environ/GROQ_API_KEY
  model_info:
    mode: audio_transcription
```

### Mistral Voxtral

```yaml
- model_name: voxtral
  litellm_params:
    model: mistral/voxtral-mini-latest
    api_key: os.environ/MISTRAL_API_KEY
  model_info:
    mode: audio_transcription
```

### Deepgram

```yaml
- model_name: deepgram-nova
  litellm_params:
    model: deepgram/nova-2
    api_key: os.environ/DEEPGRAM_API_KEY
  model_info:
    mode: audio_transcription
```

### OVHcloud AI Endpoints (data residency EU)

```yaml
- model_name: ovh-whisper
  litellm_params:
    model: ovhcloud/whisper-large-v3
    api_key: os.environ/OVHCLOUD_API_KEY
  model_info:
    mode: audio_transcription
```

## Guardrails sur le texte transcrit

S'applique uniquement en non-streaming (le texte complet doit être disponible avant le check). Configuration via Presidio (PII), Lakera, AIM, etc. — voir skill `litellm-guardrails-policies`.

```yaml
guardrails:
  - guardrail_name: presidio-pii-output
    litellm_params:
      guardrail: presidio
      mode: post_call
      apply_to:
        - whisper-stt
        - groq-whisper
```

Use case Loi 25 / IntelliSoins : transcription d'audio clinique → masquage PII (nom patient, NAS, dates) avant logging Langfuse.

## Anti-patterns

1. **Oublier `mode: audio_transcription`** dans `model_info` → router envoie sur `chat/completions` → 4xx obscur.
2. **Streaming + guardrails** → guardrails ne s'appliquent pas en streaming pour cet endpoint (limitation upstream).
3. **Hardcoder la master key** dans un script Python ou `.env` projet → utiliser Keychain (`security find-generic-password`).
4. **Appeler `whisper-stt` sans `aictl start`** → backend MLX DOWN par défaut, requête timeout.
5. **`Content-Type: application/json`** + path en string → 400. Toujours `multipart/form-data` + binaire.
6. **Mélanger `extra_body.fallbacks` (par requête) et `litellm_settings.fallbacks` (global) sans comprendre la précédence** → la valeur par requête écrase la valeur globale pour cette requête.

## Troubleshooting

| Symptôme                                       | Cause probable                                                       | Fix                                                                           |
| ---------------------------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `404 Not Found` sur `/v1/audio/transcriptions` | `mode: audio_transcription` manquant dans `model_info`               | Ajouter dans config.yaml + restart proxy                                      |
| `400 Bad Request` "file required"              | Multipart mal formé                                                  | Vérifier `--form 'file=@"path"'` (curl) ou `file=open(p, "rb")` (Python)      |
| Timeout sur `whisper-stt` local                | Backend MLX DOWN                                                     | `aictl start whisper-stt` puis `aictl status`                                 |
| Fallback ne se déclenche pas                   | Le primary retourne 200 avec body vide → pas considéré comme failure | Ajouter health check upstream (skill `litellm-routing-fallbacks` § cooldowns) |
| Cost tracking absent dans Admin UI             | Provider ne retourne pas d'usage info pour audio                     | Configurer `model_info.input_cost_per_second` manuellement                    |

## Cross-references

| Skill                                          | Quand consulter                                                     |
| ---------------------------------------------- | ------------------------------------------------------------------- |
| `litellm-routing-fallbacks`                    | Fallbacks avancés, cooldowns, retries, A/B testing                  |
| `litellm-config-yaml`                          | Référence complète `model_list` / `model_info` / `litellm_settings` |
| `litellm-guardrails-policies`                  | Presidio/Lakera sur le texte transcrit (Loi 25)                     |
| `litellm-logging-metrics`                      | Trace Langfuse / OTel pour transcriptions                           |
| `litellm-providers-models`                     | Liste exhaustive des modèles audio par provider                     |
| `intellisoins-infrastructure:local-ai-servers` | Gestion `aictl` pour démarrer `whisper-stt`                         |

Rules :

- `~/.claude/rules/local-ai-stack.md` — proxy port 8092, Keychain, MLX DOWN par défaut
- `~/ai-servers/litellm-proxy/config.yaml:206-216` — config audio actuelle (whisper-stt + kokoro-tts)

## Endpoints connexes (hors scope de ce skill)

- `/v1/audio/speech` — Text-to-Speech (cf. `kokoro-tts` dans le proxy local, port 8880)
- `/v1/audio/translations` — Transcription + traduction vers anglais

À couvrir dans un skill séparé si besoin (`litellm-audio-speech`, `litellm-audio-translations`).
