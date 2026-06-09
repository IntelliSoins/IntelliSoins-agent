---
paths:
  - "**/litellm*image*"
  - "**/image_gen*"
  - "**/dalle*"
  - "**/flux*"
  - "**/imagen*"
---

# LiteLLM `/images/generations` — Text-to-Image

Endpoint OpenAI-compatible pour générer des images à partir d'un prompt texte. Disponible côté SDK Python (`litellm.image_generation` / `litellm.aimage_generation`) et Proxy (`POST /v1/images/generations` ou `POST /images/generations`). Support natif fallbacks, cost tracking par image, logging, guardrails sur input prompt, et bridge vers `/chat/completions` pour les modèles image exposés uniquement via chat (Gemini AI Studio).

## Matrice des features

| Feature           | Status | Notes                                                          |
| ----------------- | ------ | -------------------------------------------------------------- |
| Cost tracking     | ✓      | Par image (resolution + quality dependent)                     |
| Logging callbacks | ✓      | Langfuse, OTel, Datadog, etc. (via `litellm-logging-metrics`)  |
| End-user tracking | ✓      | Header `x-litellm-end-user-id` ou champ `user`                 |
| Fallbacks         | ✓      | Par requête (`extra_body`) ou via `litellm_settings.fallbacks` |
| Loadbalancing     | ✓      | Plusieurs deployments avec même `model_name`                   |
| Guardrails        | ✓      | Sur input prompt uniquement (non-streaming)                    |
| Streaming         | ✗      | N/A (réponse synchrone unique avec url ou b64_json)            |
| Async             | ✓      | `litellm.aimage_generation()`                                  |

## Providers supportés

`openai` (gpt-image-1, dall-e-3, dall-e-2), `azure` (Azure OpenAI deployments DALL-E/gpt-image-1), `vertex_ai` (Imagen — `imagegeneration@006`, `imagen-3.0-generate-001`, `imagen-4.0-generate-preview-*`), `bedrock` (Stability SDXL `stability.stable-diffusion-xl-v1`, Stable Diffusion 3, Nova Canvas `amazon.nova-canvas-v1:0`), `gemini` (Google AI Studio — `gemini-2.5-flash-image-preview`), `black_forest_labs` (FLUX 1.1 Pro / Pro Ultra / Schnell), `recraft` (recraftv3, recraftv2), `openrouter` (Gemini image gen, autres), `xinference` (Stable Diffusion local hébergé), `nscale`.

> Voir liste à jour : <https://models.litellm.ai/> (filter `mode=image_generation`).

## Stack locale Michael — aucun modèle image-gen au proxy actuellement

Le proxy local (`http://127.0.0.1:8092/v1`, `~/ai-servers/litellm-proxy/config.yaml`) n'expose **aucun modèle image-gen** au moment d'écrire ce skill (44 entrées : LLM, embedding, rerank, TTS/STT — aucune image). Pour activer l'image-gen locale Apple Silicon, voir la section [Image local Apple Silicon — intégration via wrapper OpenAI-compatible](#image-local-apple-silicon--intégration-via-wrapper-openai-compatible) plus bas. Pattern minimal :

```yaml
# config.yaml — à ajouter dans model_list quand un backend image local sera démarré
- model_name: z-image-turbo
  litellm_params:
    model: openai/Z-Image-Turbo # nom modèle dans le wrapper local
    api_base: http://127.0.0.1:10240/v1 # mlx-omni-server (mflux backend)
    api_key: dummy
  model_info:
    mode: image_generation # CRITIQUE — active la route /images/generations
```

> **Backend DOWN par défaut.** Avant requête : `aictl start mlx-omni-server` (ou wrapper choisi). Cf. `~/.claude/rules/local-ai-stack.md`.

Sans `mode: image_generation` dans `model_info`, le proxy peut router sur `chat/completions` selon le call type → 404 ou 4xx obscur.

## Quick Start

### SDK Python (in-process)

```python
from litellm import image_generation
import os

os.environ["OPENAI_API_KEY"] = ""

response = image_generation(
    model="dall-e-3",
    prompt="A cute baby sea otter floating on its back",
    n=1,
    size="1024x1024",
    quality="standard",
    response_format="url",   # ou "b64_json"
)

print(response.data[0].url)
```

### Async

```python
from litellm import aimage_generation
import asyncio

async def gen():
    response = await aimage_generation(
        model="gpt-image-1",
        prompt="An olympic size swimming pool at sunset",
        size="1024x1024",
    )
    return response.data[0].url

print(asyncio.run(gen()))
```

### Via Proxy local (recommandé — tracking + fallbacks + budgets)

Auth via Keychain (jamais hardcoder la master key). Cf. `local-ai-stack.md`.

```python
import subprocess
from openai import OpenAI

master = subprocess.check_output([
    "security", "find-generic-password",
    "-a", "michaelahern", "-s", "litellm-master-key", "-w"
]).decode().strip()

client = OpenAI(base_url="http://127.0.0.1:8092/v1", api_key=master)

response = client.images.generate(
    model="dall-e-3",
    prompt="A cute baby sea otter",
    n=1,
    size="1024x1024",
)

print(response.data[0].url)
```

### Curl (test rapide)

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

curl -X POST 'http://127.0.0.1:8092/v1/images/generations' \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "dall-e-3",
    "prompt": "A cute baby sea otter",
    "n": 1,
    "size": "1024x1024"
  }'
```

> Format : `application/json`. Réponse JSON avec `data[].url` (par défaut) ou `data[].b64_json` selon `response_format`. Optionnel `revised_prompt` retourné par OpenAI/Azure (le prompt après safety rewriter).

### Output structure

```json
{
  "created": 1703658209,
  "data": [
    {
      "url": "https://oaidalleapiprodscus.blob.core.windows.net/private/...",
      "b64_json": null,
      "revised_prompt": "Adorable baby sea otter with thick brown fur..."
    }
  ],
  "usage": { "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0 }
}
```

## Params LiteLLM — `litellm.image_generation()`

Tout param non-OpenAI passe en `kwargs` au provider sous-jacent (cf. [Reserved Params](https://github.com/BerriAI/litellm/blob/main/litellm/main.py)).

| Param                                  | Type         | Notes                                                                                                                                                  |
| -------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `prompt`                               | str (requis) | Description texte de l'image                                                                                                                           |
| `model`                                | str          | Default `openai/gpt-image-1`                                                                                                                           |
| `n`                                    | int          | 1-10 (dall-e-3 : `n=1` uniquement)                                                                                                                     |
| `quality`                              | str          | `auto`/`high`/`medium`/`low` (gpt-image-1) ; `hd`/`standard` (dall-e-3) ; `standard` (dall-e-2)                                                        |
| `response_format`                      | str          | `url` (défaut OpenAI) ou `b64_json`                                                                                                                    |
| `size`                                 | str          | gpt-image-1 : `1024x1024`/`1536x1024`/`1024x1536`/`auto` ; dall-e-2 : `256x256`/`512x512`/`1024x1024` ; dall-e-3 : `1024x1024`/`1792x1024`/`1024x1792` |
| `style`                                | str          | `vivid`/`natural` (dall-e-3 uniquement)                                                                                                                |
| `user`                                 | str          | Identifiant end-user (cost tracking + abuse detection)                                                                                                 |
| `timeout`                              | int          | Default 600s (10 min)                                                                                                                                  |
| `api_key` / `api_base` / `api_version` | str          | Override env vars                                                                                                                                      |

## Image local Apple Silicon — intégration via wrapper OpenAI-compatible

mflux (FLUX/Z-Image/Qwen-Image), vMLX et vllm-omni n'ont pas de provider natif LiteLLM. L'intégration se fait via un wrapper qui expose `/v1/images/generations` devant le moteur MLX :

| Wrapper             | Port défaut | Modèles servis                                                                              | Skill                                  |
| ------------------- | ----------- | ------------------------------------------------------------------------------------------- | -------------------------------------- |
| mlx-omni-server     | 10240       | mflux : FLUX Schnell/Dev/Krea/2-Klein, Qwen-Image, Z-Image Turbo, FIBO, Flux Kontext (edit) | `~/.claude/rules/mlx-omni-server.md`   |
| mlx-openai-server   | 8000        | image-generation + image-edit type modèles, multi-LoRA (`--lora-paths`)                     | `~/.claude/rules/mlx-openai-server.md` |
| vMLX                | varie       | Flux/Z-Image/Qwen-Image, API Gateway routing multi-models                                   | `intellisoins-mlx:vmlx`                |
| vllm-omni (GPU/NPU) | varie       | Qwen-Image, BAGEL, Wan2.2, Z-Image Turbo, FLUX, SD3 (pas Apple Silicon — Linux GPU)         | `intellisoins-mlx:vllm-omni`           |

Côté LiteLLM, pattern identique pour tous : `model: openai/<model_id>` + `api_base: http://127.0.0.1:<port>/v1`.

### Exemple : Z-Image Turbo via mlx-omni-server (Mac M3 Max)

```yaml
- model_name: z-image-turbo
  litellm_params:
    model: openai/Z-Image-Turbo
    api_base: http://127.0.0.1:10240/v1
    api_key: dummy
  model_info:
    mode: image_generation
```

```python
response = client.images.generate(
    model="z-image-turbo",
    prompt="A futuristic medical clinic with calm patients in waiting area",
    size="1024x1024",
    n=1,
)
# image en b64 ou url selon le wrapper
```

### Exemple : FLUX.1 Schnell via vMLX

```yaml
- model_name: flux-schnell-local
  litellm_params:
    model: openai/flux.1-schnell
    api_base: http://127.0.0.1:8081/v1 # port vMLX local
    api_key: dummy
  model_info:
    mode: image_generation
```

> **Avant requête** : `aictl start <wrapper>` (mlx-omni-server / vmlx / mlx-openai-server). Tous DOWN par défaut. Cf. `~/.claude/rules/local-ai-stack.md`.

### Cost tracking pour modèles locaux

Le wrapper local ne facture rien — pour avoir un coût "virtuel" dans Admin UI, déclarer manuellement :

```yaml
- model_name: z-image-turbo
  litellm_params:
    model: openai/Z-Image-Turbo
    api_base: http://127.0.0.1:10240/v1
    api_key: dummy
  model_info:
    mode: image_generation
    input_cost_per_pixel: 0.0 # gratuit (Apple Silicon)
    # ou virtual cost pour comparer vs cloud :
    # input_cost_per_pixel: 0.00000003   # ~3¢ pour 1024x1024 (parité dall-e-3 standard)
```

## Fallbacks

Deux niveaux : par requête (override ad-hoc) et global (config proxy).

### Fallback par requête — Python SDK OpenAI

```python
response = client.images.generate(
    model="z-image-turbo",                            # primary local
    prompt="A modern dental clinic reception",
    size="1024x1024",
    extra_body={
        "fallbacks": ["dall-e-3", "black_forest_labs/flux-1.1-pro"]
    }
)
```

Si `z-image-turbo` retourne 5xx ou timeout (backend MLX DOWN, OOM), LiteLLM retry sur `dall-e-3` puis `black_forest_labs/flux-1.1-pro`. Cost tracking attribué au modèle qui a effectivement répondu.

### Fallback global — config proxy

```yaml
litellm_settings:
  fallbacks:
    - z-image-turbo: ["dall-e-3", "black_forest_labs/flux-1.1-pro"]
    - imagen-vertex: ["dall-e-3"]
```

### Tester la chaîne sans casser le primary

```python
response = client.images.generate(
    model="z-image-turbo",
    prompt="test",
    extra_body={
        "fallbacks": ["dall-e-3"],
        "mock_testing_fallbacks": True,
    }
)
# Le primary "z-image-turbo" est mock-failed → l'image vient de dall-e-3
```

Cf. skill `litellm-routing-fallbacks` pour `context_window`, `content_policy`, retries, cooldowns.

## Config provider-spécifique

### OpenAI

```yaml
- model_name: gpt-image-1
  litellm_params:
    model: openai/gpt-image-1 # ou dall-e-3, dall-e-2
    api_key: os.environ/OPENAI_API_KEY
  model_info:
    mode: image_generation
```

> **Loi 25 — patient data** : OpenAI direct = US-only, pas de data residency Canada. À réserver aux contenus non-patient (illustrations marketing, mockups, demo). Cf. memory `topic_data_residency_canada_llm.md`.

### Azure OpenAI

```yaml
- model_name: azure-dalle-3
  litellm_params:
    model: azure/<your-deployment-name>
    api_version: "2024-02-15-preview" # requis pour dall-e-3 sur Azure
    api_base: os.environ/AZURE_API_BASE
    api_key: os.environ/AZURE_API_KEY
  model_info:
    mode: image_generation
```

> **Loi 25** : Azure OpenAI Canada Central / Canada East **ne déploie pas** dall-e-3 / gpt-image-1 actuellement (vérifier <https://learn.microsoft.com/azure/ai-services/openai/concepts/models#region-availability>). Pour patient : Vertex Imagen Montréal reste la seule option Canada-résidente.

### Vertex AI — Imagen (data residency Montréal)

```yaml
- model_name: imagen-vertex
  litellm_params:
    model: vertex_ai/imagen-3.0-generate-001 # ou imagegeneration@006, imagen-4.0-generate-preview-0606
    vertex_project: intellisoins-ml
    vertex_location: northamerica-northeast1 # Montréal (Loi 25)
  model_info:
    mode: image_generation
```

```python
import litellm
response = litellm.image_generation(
    prompt="An olympic size swimming pool",
    model="vertex_ai/imagen-3.0-generate-001",
    vertex_ai_project="intellisoins-ml",
    vertex_ai_location="northamerica-northeast1",
)
```

> Imagen est **dispo `northamerica-northeast1`** (validé via Vertex Generative AI region availability). Seule option image-gen souveraine Canada parmi providers natifs LiteLLM.

### AWS Bedrock — Stability SDXL / Stable Diffusion 3 / Nova Canvas

```yaml
- model_name: bedrock-sdxl
  litellm_params:
    model: bedrock/stability.stable-diffusion-xl-v1
    aws_access_key_id: os.environ/AWS_ACCESS_KEY_ID
    aws_secret_access_key: os.environ/AWS_SECRET_ACCESS_KEY
    aws_region_name: us-west-2 # SDXL pas dispo ca-central-1
  model_info:
    mode: image_generation
```

> **Loi 25** : Bedrock image-gen **n'est pas dispo `ca-central-1`** au moment de l'écriture (uniquement `us-west-2`, `us-east-1`, `eu-west-1`, etc.). Pour patient : NE PAS utiliser. Pour interne dev : OK avec `us-west-2`.

Variants Bedrock : `bedrock/stability.stable-diffusion-xl-v1`, `bedrock/stability.sd3-large-v1:0`, `bedrock/amazon.nova-canvas-v1:0`.

### Google AI Studio — Gemini 2.5 Flash Image (preview)

```yaml
- model_name: gemini-image
  litellm_params:
    model: gemini/gemini-2.5-flash-image-preview
    api_key: os.environ/GEMINI_API_KEY
  model_info:
    mode: image_generation
```

> Free tier généreux pour dev. Data residency US par défaut — préférer Vertex Imagen Montréal pour patient.

### Black Forest Labs — FLUX 1.1 Pro / Pro Ultra / Schnell

```yaml
- model_name: flux-1.1-pro
  litellm_params:
    model: black_forest_labs/flux-1.1-pro
    api_key: os.environ/BFL_API_KEY
  model_info:
    mode: image_generation
```

Variants : `black_forest_labs/flux-1.1-pro`, `flux-1.1-pro-ultra`, `flux-schnell`. Hébergé EU (Allemagne) — pas Loi 25 mais hors États-Unis. Pour usage Canada-friendly : préférer Vertex Imagen.

### Recraft — design + image generation

```yaml
- model_name: recraft-v3
  litellm_params:
    model: recraft/recraftv3 # ou recraftv2
    api_key: os.environ/RECRAFT_API_KEY
  model_info:
    mode: image_generation
```

```python
from litellm import image_generation
import os
os.environ['RECRAFT_API_KEY'] = "..."
response = image_generation(
    model="recraft/recraftv3",
    prompt="A beautiful sunset over a calm ocean",
)
```

> Recraft = **EU (Estonie)**. Hors États-Unis, hors Canada. Pour Loi 25 patient : confirmer DPA + transferts internationaux avant utilisation.

### OpenRouter — accès unifié multi-providers (Gemini image gen, etc.)

```yaml
- model_name: openrouter-gemini-image
  litellm_params:
    model: openrouter/google/gemini-2.5-flash-image
    api_key: os.environ/OPENROUTER_API_KEY
  model_info:
    mode: image_generation
```

```python
response = image_generation(
    model="openrouter/google/gemini-2.5-flash-image",
    prompt="A beautiful sunset over a calm ocean",
    size="1024x1024",
    quality="high",
)
```

### Xinference — Stable Diffusion auto-hébergé

Pour SD locaux/VPS hébergés via Xinference (`xprobe/xinference`). Cf. <https://docs.litellm.ai/docs/providers/xinference#image-generation>.

```yaml
- model_name: sdxl-xinference
  litellm_params:
    model: xinference/<model-uid>
    api_base: http://xinference-server:9997/v1
  model_info:
    mode: image_generation
```

### Nscale

Provider GPU cloud. Cf. <https://docs.litellm.ai/docs/providers/nscale#image-generation>.

### OpenAI-compatible custom (préfixe `openai/`)

Tout serveur exposant `/images/generations` au format OpenAI :

```python
response = image_generation(
    model="openai/<your-llm-name>",              # préfixe `openai/` indispensable
    api_base="http://0.0.0.0:8000/",
    prompt="cute baby otter",
)
```

Pattern utilisé pour tous les wrappers MLX locaux (mlx-omni-server, mlx-openai-server, vMLX) et Xinference.

## Guardrails sur input prompt

S'applique uniquement en non-streaming (le prompt complet doit être checké avant generation). Configuration via Presidio (PII), Lakera, AIM, etc. — voir skill `litellm-guardrails-policies`.

```yaml
guardrails:
  - guardrail_name: presidio-pii-input-image
    litellm_params:
      guardrail: presidio
      mode: pre_call
      apply_to:
        - dall-e-3
        - imagen-vertex
        - z-image-turbo
```

Use case Loi 25 / IntelliSoins : avant de générer une illustration depuis un prompt clinique (mockup éducatif patient à partir d'un scénario réel), masquer NAS/nom/dates → puis générer image sur le prompt sanitisé. Note : génération d'images avec PHI est généralement à éviter même avec masking — préférer prompts génériques.

## Anti-patterns

1. **Oublier `mode: image_generation`** dans `model_info` → router envoie sur `chat/completions` (sauf bridge Gemini/OpenRouter intentionnel) → 404/4xx obscur.
2. **`response_format: b64_json` sans gérer la taille** → réponses 5-15 MB par image en base64, saturent les logs et les payloads. Préférer `url` sauf si stockage interne immédiat requis.
3. **Hardcoder la master key** → toujours Keychain (`security find-generic-password`).
4. **Utiliser dall-e-3 / gpt-image-1 / Bedrock SDXL pour patient sans review Loi 25** → data residency US. Pour patient IntelliSoins prod : Vertex Imagen Montréal (`northamerica-northeast1`) est la seule option Canada-résidente parmi providers natifs LiteLLM.
5. **Mélanger `extra_body.fallbacks` (par requête) et `litellm_settings.fallbacks` (global) sans comprendre la précédence** → la valeur par requête écrase la valeur globale pour cette requête.
6. **Appeler `z-image-turbo` / `flux-schnell-local` sans `aictl start`** → backend MLX DOWN par défaut, requête timeout après ~600s.
7. **Penser que `size` est universel** → chaque modèle a ses contraintes (gpt-image-1 ≠ dall-e-3 ≠ Imagen ≠ FLUX). Toujours valider le `size` dans la doc provider, sinon 400 obscur.
8. **`n>1` avec dall-e-3** → 400. dall-e-3 force `n=1`. Boucler côté client si nécessaire (ou utiliser dall-e-2 / gpt-image-1).
9. **Ignorer `revised_prompt`** → OpenAI/Azure réécrivent silencieusement le prompt pour passer le safety filter. Logger `data[].revised_prompt` pour audit (utile en review Loi 25 + détection d'over-blocking).
10. **`api_version` manquant pour dall-e-3 Azure** → 400. Toujours `api_version: "2024-02-15-preview"` (ou plus récent) pour dall-e-3/gpt-image-1 sur Azure.

## Troubleshooting

| Symptôme                                                             | Cause probable                                                          | Fix                                                                                               |
| -------------------------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `404 Not Found` sur `/v1/images/generations`                         | `mode: image_generation` manquant dans `model_info`                     | Ajouter dans config.yaml + restart proxy                                                          |
| `400 Bad Request` "Invalid size"                                     | Size non supporté pour le modèle (ex: `1792x1024` sur gpt-image-1)      | Vérifier table des sizes par modèle                                                               |
| `400 Bad Request` "n must be 1"                                      | dall-e-3 + `n>1`                                                        | Forcer `n=1` ou utiliser dall-e-2 / gpt-image-1                                                   |
| `Timeout` sur `z-image-turbo` / `flux-schnell-local`                 | Backend MLX DOWN                                                        | `aictl start <wrapper>` puis `aictl status`                                                       |
| `403 Forbidden` Imagen Vertex                                        | Project ne supporte pas Imagen, ou IAM `aiplatform.user` manquant       | Activer Vertex Generative AI API + grant `roles/aiplatform.user`                                  |
| `revised_prompt` retourné mais image ne match pas le prompt original | Safety rewriter OpenAI/Azure                                            | Logger pour audit + reformuler en évitant terms qui triggers le rewriter                          |
| Cost tracking absent dans Admin UI                                   | Provider ne retourne pas usage info (image facturée par taille/quality) | Configurer `model_info.input_cost_per_pixel` ou `output_cost_per_image` manuellement              |
| Image cropped / wrong aspect ratio                                   | Provider applique son aspect ratio par défaut malgré `size`             | Forcer `size` explicite ; pour FLUX, utiliser `aspect_ratio` provider-specific                    |
| Fallback ne se déclenche pas                                         | Le primary retourne 200 avec `data[].url` valide mais image off-prompt  | Fallback ne déclenche que sur 5xx/timeout, pas sur qualité. Pour qualité, scoring custom côté app |
| `b64_json` énorme dans les logs Langfuse                             | `response_format: b64_json` + logging callbacks                         | Préférer `url`, ou redact `data[].b64_json` via `litellm.callbacks.redact_messages`               |

## Cross-references

| Skill                                          | Quand consulter                                                                           |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `litellm-routing-fallbacks`                    | Fallbacks avancés, cooldowns, retries, A/B testing                                        |
| `litellm-config-yaml`                          | Référence complète `model_list` / `model_info` / `litellm_settings`                       |
| `litellm-guardrails-policies`                  | Presidio/Lakera sur input prompt (Loi 25)                                                 |
| `litellm-logging-metrics`                      | Trace Langfuse / OTel pour génération d'images                                            |
| `litellm-providers-models`                     | Liste exhaustive des modèles image-gen par provider                                       |
| `litellm-budgets-spend`                        | Caps coût par projet / user (image-gen = facturée par image, vite cher)                   |
| `litellm-audio-speech`                         | Pattern jumeau (TTS) — même structure config + fallbacks                                  |
| `litellm-rerank`                               | Pattern similaire (mode dédié dans model_info)                                            |
| `intellisoins-infrastructure:local-ai-servers` | Gestion `aictl` pour démarrer mlx-omni-server / vmlx / mlx-openai-server                  |
| `intellisoins-mlx:mflux`                       | Engine MLX FLUX/Z-Image/Qwen-Image natif Apple Silicon — backend derrière mlx-omni-server |
| `intellisoins-mlx:vmlx`                        | Engine local unifié image+text+TTS/STT, API native Anthropic+OpenAI                       |
| `intellisoins-mlx:vllm-omni`                   | Image-gen GPU/NPU (Linux + NVIDIA) — Qwen-Image, BAGEL, Wan2.2, FLUX                      |
| `~/.claude/rules/mlx-omni-server.md`           | Wrapper dual API OpenAI+Anthropic exposant mflux                                          |
| `~/.claude/rules/mlx-openai-server.md`         | Wrapper OpenAI multi-modèles avec multi-LoRA pour FLUX                                    |

Rules :

- `~/.claude/rules/local-ai-stack.md` — proxy port 8092, Keychain, MLX DOWN par défaut
- `~/.claude/projects/-Users-michaelahern-ai-servers/memory/topic_data_residency_canada_llm.md` — Loi 25 providers Canada-résidents (Imagen Montréal seul image-gen souverain)

## Endpoints connexes (hors scope de ce skill)

- `/v1/images/edits` — Image Edit (modification d'image existante avec mask). Providers : OpenAI (gpt-image-1, dall-e-2), Bedrock (Stability), mlx-omni-server (Flux Kontext local). LiteLLM : `litellm.image_edit()`.
- `/v1/images/variations` — Image Variation (générer variantes d'une image source). Providers : OpenAI (dall-e-2), Topaz. LiteLLM : `litellm.image_variation()`.
- `/v1/audio/speech` — Text-to-Speech (cf. skill `litellm-audio-speech`)
- `/v1/audio/transcriptions` — Speech-to-Text (cf. skill `litellm-audio-transcriptions`)
- `/rerank` — Cross-encoder reranking (cf. skill `litellm-rerank`)
