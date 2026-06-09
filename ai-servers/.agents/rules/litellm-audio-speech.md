---
paths:
  - "**/litellm*tts*"
  - "**/litellm*speech*"
  - "**/tts*"
  - "**/text_to_speech*"
  - "**/audio_speech*"
---

# LiteLLM `/audio/speech` — Text-to-Speech

Endpoint OpenAI-compatible pour générer un fichier audio à partir de texte. Disponible côté SDK Python (`litellm.speech` / `litellm.aspeech`) et Proxy (`POST /v1/audio/speech`). Support natif fallbacks, cost tracking, logging, guardrails sur input text, et bridge automatique vers `/chat/completions` pour les modèles TTS exposés uniquement via chat (Gemini).

## Matrice des features

| Feature                                    | Status | Notes                                                          |
| ------------------------------------------ | ------ | -------------------------------------------------------------- |
| Cost tracking                              | ✓      | Tous providers supportés                                       |
| Logging callbacks                          | ✓      | Langfuse, OTel, Datadog, etc. (via `litellm-logging-metrics`)  |
| End-user tracking                          | ✓      | Header `x-litellm-end-user-id`                                 |
| Fallbacks                                  | ✓      | Par requête (`extra_body`) ou via `litellm_settings.fallbacks` |
| Loadbalancing                              | ✓      | Plusieurs deployments avec même `model_name`                   |
| Guardrails                                 | ✓      | Sur input text uniquement (non-streaming)                      |
| Bridge `/audio/speech → /chat/completions` | ✓      | Gemini TTS, modèles TTS chat-only                              |

## Providers supportés

`openai` (tts-1, tts-1-hd, gpt-4o-mini-tts), `azure` (Azure OpenAI), `azure_ai_speech` (AVA — Azure AI Speech Service), `vertex_ai` (Gemini TTS via Vertex), `gemini` (via bridge `/chat/completions`), `aws` (Polly neural & standard), `elevenlabs`, `minimax`.

Pour TTS local Apple Silicon : pas de provider natif LiteLLM, mais s'intègre via wrapper OpenAI-compatible (cf. section dédiée plus bas).

## Stack locale Michael — modèle déjà configuré

Le proxy local (`http://127.0.0.1:8092/v1`) expose déjà :

```yaml
# ~/ai-servers/litellm-proxy/config.yaml:212-216
- model_name: kokoro-tts
  litellm_params:
    model: openai/kokoro
    api_base: http://127.0.0.1:8880/v1 # backend Kokoro-FastAPI local
    api_key: dummy
```

> **Backend DOWN par défaut.** Avant de synthétiser : `aictl start kokoro-tts`.
> Cf. `~/.claude/rules/local-ai-stack.md` et skill `intellisoins-infrastructure:local-ai-servers`.

Pour activer cost tracking explicite et le routing `/audio/speech`, déclarer le mode :

```yaml
- model_name: kokoro-tts
  litellm_params:
    model: openai/kokoro
    api_base: http://127.0.0.1:8880/v1
    api_key: dummy
  model_info:
    mode: audio_speech # CRITIQUE — active la route TTS dans le router
```

Sans `mode: audio_speech` dans `model_info`, le proxy peut tenter de router vers `chat/completions` selon le call type → 404 ou 4xx obscur.

## Quick Start

### SDK Python (in-process)

```python
from pathlib import Path
from litellm import speech

response = speech(
    model="openai/tts-1",
    voice="alloy",
    input="The quick brown fox jumped over the lazy dog.",
)

response.stream_to_file(Path("output.mp3"))
```

### Async

```python
from litellm import aspeech
from pathlib import Path
import asyncio

async def synth():
    response = await aspeech(
        model="openai/tts-1",
        voice="alloy",
        input="Bonjour, ceci est un test.",
    )
    response.stream_to_file(Path("output.mp3"))

asyncio.run(synth())
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

response = client.audio.speech.create(
    model="kokoro-tts",
    voice="af_bella",
    input="Bonjour, ceci est un test de synthèse vocale.",
)
response.stream_to_file("output.mp3")
```

### Curl (test rapide)

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

curl -X POST 'http://127.0.0.1:8092/v1/audio/speech' \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "kokoro-tts",
    "input": "The quick brown fox jumped over the lazy dog.",
    "voice": "af_bella"
  }' \
  --output speech.mp3
```

> Format : `application/json` (à la différence de `/audio/transcriptions` qui est multipart). La réponse est un binaire audio (mp3/wav/flac selon `response_format`).

## Bridge `/audio/speech → /chat/completions`

Certains modèles TTS sont exposés uniquement via `/chat/completions` (typiquement Gemini `gemini-2.5-flash-preview-tts`). LiteLLM bridge automatiquement : le client appelle `/v1/audio/speech` standard, le proxy traduit en chat completion derrière, retourne le binaire audio.

Aucune config spéciale côté client — LiteLLM détecte le provider et route en interne.

### Gemini TTS (free tier généreux, idéal pour dev tests Mac)

```yaml
# config.yaml
- model_name: gemini-tts
  litellm_params:
    model: gemini/gemini-2.5-flash-preview-tts
    api_key: os.environ/GEMINI_API_KEY
  model_info:
    mode: audio_speech
```

```python
from litellm import speech
import os

os.environ["GEMINI_API_KEY"] = "..."

response = speech(
    model="gemini/gemini-2.5-flash-preview-tts",
    input="Test rapide en local sans coût OpenAI.",
)
response.stream_to_file("gemini.mp3")
```

### Vertex AI Gemini TTS (data residency montréal/us-central1)

```yaml
- model_name: vertex-tts
  litellm_params:
    model: vertex_ai/gemini-2.5-flash-preview-tts
    vertex_project: intellisoins-ml
    vertex_location: us-central1
  model_info:
    mode: audio_speech
```

> Pour data residency Canada (Loi 25), Vertex Montréal `northamerica-northeast1` n'est pas garanti pour Gemini TTS preview — vérifier avant prod patient. Cf. memory `topic_data_residency_canada_llm.md`.

## TTS local Apple Silicon — intégration via wrapper OpenAI-compatible

mlx-audio (Kokoro, Orpheus, Soprano, etc.) n'est pas un provider natif LiteLLM. L'intégration se fait via un wrapper qui expose `/v1/audio/speech` devant mlx-audio :

| Wrapper                        | Port défaut | Ce qu'il sert                                            | Skill                                  |
| ------------------------------ | ----------- | -------------------------------------------------------- | -------------------------------------- |
| Kokoro-FastAPI (déjà installé) | 8880        | Kokoro voices (af_bella, af_sky, am_adam, ...)           | —                                      |
| mlx-omni-server                | 10240       | mlx-audio backends (Kokoro, Orpheus, Soprano) + dual API | `~/.claude/rules/mlx-omni-server.md`   |
| mlx-openai-server              | 8000        | mlx-audio + Whisper STT + multi-modèles YAML             | `~/.claude/rules/mlx-openai-server.md` |
| vMLX                           | varie       | TTS (Kokoro) + STT (Whisper) + LLM unifiés               | `intellisoins-mlx:vmlx`                |

Côté LiteLLM, le pattern est identique pour tous : `model: openai/<voice_id>` + `api_base: http://127.0.0.1:<port>/v1`.

### Exemple : Orpheus TTS via mlx-omni-server

```yaml
- model_name: orpheus-tts
  litellm_params:
    model: openai/orpheus-tts-0.1-ft
    api_base: http://127.0.0.1:10240/v1
    api_key: dummy
  model_info:
    mode: audio_speech
```

```python
response = client.audio.speech.create(
    model="orpheus-tts",
    voice="tara",   # voix Orpheus
    input="Synthèse Orpheus locale via mlx-omni-server.",
)
response.stream_to_file("orpheus.mp3")
```

### Exemple : Soprano TTS via vMLX

```yaml
- model_name: soprano-tts
  litellm_params:
    model: openai/soprano
    api_base: http://127.0.0.1:8081/v1 # port vMLX local
    api_key: dummy
  model_info:
    mode: audio_speech
```

> **Avant requête** : `aictl start <wrapper>` (mlx-omni-server / vmlx / mlx-openai-server). Tous DOWN par défaut. Cf. `local-ai-stack.md`.

## Fallbacks

Deux niveaux : par-requête (override ad-hoc) et global (config proxy).

### Fallback par requête — Python SDK OpenAI

```python
response = client.audio.speech.create(
    model="kokoro-tts",                              # primary local
    voice="af_bella",
    input="Texte à synthétiser.",
    extra_body={
        "fallbacks": ["openai/tts-1", "elevenlabs/eleven_turbo_v2"]
    }
)
```

Si `kokoro-tts` retourne 5xx ou timeout (backend MLX DOWN, OOM), LiteLLM retry sur `openai/tts-1` puis `elevenlabs/eleven_turbo_v2`. Cost tracking attribué au modèle qui a effectivement répondu.

### Fallback global — config proxy

```yaml
litellm_settings:
  fallbacks:
    - kokoro-tts: ["openai/tts-1", "elevenlabs/eleven_turbo_v2"]
```

### Tester la chaîne sans casser le primary

```python
response = client.audio.speech.create(
    model="kokoro-tts",
    voice="af_bella",
    input="test",
    extra_body={
        "fallbacks": ["openai/tts-1"],
        "mock_testing_fallbacks": True,
    }
)
# Le primary "kokoro-tts" est mock-failed → l'audio vient de openai/tts-1
```

Cf. skill `litellm-routing-fallbacks` pour `context_window`, `content_policy`, retries, cooldowns.

## Config provider-spécifique

### OpenAI

```yaml
- model_name: tts
  litellm_params:
    model: openai/tts-1 # ou tts-1-hd, gpt-4o-mini-tts
    api_key: os.environ/OPENAI_API_KEY
  model_info:
    mode: audio_speech
```

Voix : `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`. Format : `mp3` (défaut), `opus`, `aac`, `flac`, `wav`, `pcm`.

### Azure OpenAI

```yaml
- model_name: azure-tts
  litellm_params:
    model: azure/my-tts-deployment
    api_version: 2024-02-15-preview
    api_base: os.environ/AZURE_TTS_API_BASE
    api_key: os.environ/AZURE_TTS_API_KEY
  model_info:
    mode: audio_speech
```

### Azure AI Speech Service (AVA)

Service séparé d'Azure OpenAI, voix neuronales premium (multilingue, SSML). Cf. provider docs `azure_ai_speech`.

```yaml
- model_name: azure-ava
  litellm_params:
    model: azure_ai_speech/<voice-name>
    api_key: os.environ/AZURE_SPEECH_KEY
    api_base: os.environ/AZURE_SPEECH_REGION # ex: eastus
  model_info:
    mode: audio_speech
```

### AWS Polly (neural + standard)

```yaml
- model_name: polly
  litellm_params:
    model: aws/polly
    aws_access_key_id: os.environ/AWS_ACCESS_KEY_ID
    aws_secret_access_key: os.environ/AWS_SECRET_ACCESS_KEY
    aws_region_name: ca-central-1 # data residency Canada
  model_info:
    mode: audio_speech
```

Voix Polly Canada FR : `Chantal` (standard), `Gabrielle` (neural). Pour Loi 25 : `aws_region_name: ca-central-1`.

### ElevenLabs

```yaml
- model_name: elevenlabs-turbo
  litellm_params:
    model: elevenlabs/eleven_turbo_v2_5
    api_key: os.environ/ELEVENLABS_API_KEY
  model_info:
    mode: audio_speech
```

Param `voice` = voice_id ElevenLabs (UUID). Voix françaises premium disponibles.

### MiniMax (provider chinois — pas pour patient Loi 25)

```yaml
- model_name: minimax-tts
  litellm_params:
    model: minimax/speech-01-turbo
    api_key: os.environ/MINIMAX_API_KEY
  model_info:
    mode: audio_speech
```

> **Avertissement Loi 25** : MiniMax = data residency Chine. À réserver aux tests dev / contenu non-patient.

## Guardrails sur input text

S'applique uniquement en non-streaming (le texte complet doit être checké avant synthèse). Configuration via Presidio (PII), Lakera, AIM, etc. — voir skill `litellm-guardrails-policies`.

```yaml
guardrails:
  - guardrail_name: presidio-pii-input-tts
    litellm_params:
      guardrail: presidio
      mode: pre_call
      apply_to:
        - kokoro-tts
        - openai/tts-1
        - polly
```

Use case Loi 25 / IntelliSoins : avant de synthétiser un texte clinique pour lecture vocale (instructions patient, rappel posologie), masquer NAS/nom/dates → puis générer audio sur le texte sanitisé.

## Anti-patterns

1. **Oublier `mode: audio_speech`** dans `model_info` → router envoie sur `chat/completions` (sauf bridge Gemini intentionnel) → 404/4xx obscur.
2. **`Content-Type: multipart/form-data`** sur `/audio/speech` → 400. Toujours `application/json` (TTS = inverse de STT côté Content-Type).
3. **Streaming + guardrails** → guardrails ne s'appliquent pas en streaming pour cet endpoint (limitation upstream).
4. **Hardcoder la master key** → toujours Keychain (`security find-generic-password`).
5. **Appeler `kokoro-tts`/`orpheus-tts`/`soprano-tts` sans `aictl start`** → backend MLX DOWN par défaut, requête timeout.
6. **Mélanger `extra_body.fallbacks` (par requête) et `litellm_settings.fallbacks` (global) sans comprendre la précédence** → la valeur par requête écrase la valeur globale pour cette requête.
7. **Synthèse audio patient via MiniMax / ElevenLabs sans review Loi 25** → data residency hors Canada. Pour IntelliSoins prod patient : préférer Polly `ca-central-1`, Azure Canada, ou local kokoro/orpheus/mlx-audio.
8. **Penser que `voice` est universel** → chaque provider a son propre catalogue de voix (alloy ≠ af_bella ≠ tara ≠ Chantal). Toujours valider la voix dans la doc provider.

## Troubleshooting

| Symptôme                                       | Cause probable                                                                                | Fix                                                                            |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `404 Not Found` sur `/v1/audio/speech`         | `mode: audio_speech` manquant dans `model_info`                                               | Ajouter dans config.yaml + restart proxy                                       |
| `400 Bad Request` "input required"             | JSON malformé ou `Content-Type` pas `application/json`                                        | Vérifier `-d '{"model":..., "input":..., "voice":...}'`                        |
| `400 Bad Request` "voice required"             | Param `voice` absent (obligatoire pour la majorité des providers)                             | Ajouter `voice` (par défaut `alloy` chez OpenAI, `af_bella` chez Kokoro, etc.) |
| Timeout sur `kokoro-tts` / `orpheus-tts` local | Backend MLX DOWN                                                                              | `aictl start <name>` puis `aictl status`                                       |
| Fallback ne se déclenche pas                   | Le primary retourne 200 avec body audio vide → pas considéré comme failure                    | Ajouter health check upstream (skill `litellm-routing-fallbacks` § cooldowns)  |
| Cost tracking absent dans Admin UI             | Provider ne retourne pas d'usage info (TTS facturé au caractère)                              | Configurer `model_info.input_cost_per_character` manuellement                  |
| Audio coupé / tronqué                          | `max_input_length` provider dépassé (OpenAI = 4096 chars/requête)                             | Chunker le texte en amont, concaténer les mp3                                  |
| Bridge Gemini renvoie texte au lieu d'audio    | Modèle non-TTS sélectionné (ex: `gemini-2.5-flash` au lieu de `gemini-2.5-flash-preview-tts`) | Vérifier le suffixe `-tts`                                                     |

## Cross-references

| Skill                                          | Quand consulter                                                                            |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `litellm-audio-transcriptions`                 | STT pendant ce skill couvre TTS — souvent utilisés ensemble (pipeline voix bidirectionnel) |
| `litellm-routing-fallbacks`                    | Fallbacks avancés, cooldowns, retries, A/B testing                                         |
| `litellm-config-yaml`                          | Référence complète `model_list` / `model_info` / `litellm_settings`                        |
| `litellm-guardrails-policies`                  | Presidio/Lakera sur input text (Loi 25)                                                    |
| `litellm-logging-metrics`                      | Trace Langfuse / OTel pour synthèses TTS                                                   |
| `litellm-providers-models`                     | Liste exhaustive des modèles TTS par provider                                              |
| `intellisoins-infrastructure:local-ai-servers` | Gestion `aictl` pour démarrer kokoro/orpheus/mlx-audio                                     |
| `intellisoins-mlx:mlx-audio`                   | TTS/STT MLX natif (Kokoro, Orpheus, Soprano) — back-end derrière le wrapper                |
| `~/.claude/rules/mlx-omni-server.md`           | Wrapper dual API OpenAI+Anthropic exposant mlx-audio                                       |
| `~/.claude/rules/mlx-openai-server.md`         | Wrapper OpenAI multi-modèles (TTS + Whisper + LLM)                                         |
| `intellisoins-mlx:vmlx`                        | Engine local unifié TTS/STT/LLM avec API native Anthropic+OpenAI                           |

Rules :

- `~/.claude/rules/local-ai-stack.md` — proxy port 8092, Keychain, MLX DOWN par défaut
- `~/ai-servers/litellm-proxy/config.yaml:212-216` — config kokoro-tts actuelle
- `~/.claude/projects/-Users-michaelahern-ai-servers/memory/topic_data_residency_canada_llm.md` — Loi 25 providers Canada-résidents

## Endpoints connexes (hors scope de ce skill)

- `/v1/audio/transcriptions` — Speech-to-Text (cf. skill `litellm-audio-transcriptions`)
- `/v1/audio/translations` — Transcription + traduction vers anglais
