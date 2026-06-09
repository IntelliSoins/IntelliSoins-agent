---
description: vMLX — référence API complète (endpoints chat/messages/embeddings/rerank/images/audio/cluster, options CLI serve+convert, VLM, agentic tools, intégration OpenClaw, troubleshooting). Sous-rule de ~/.claude/rules/vmlx.md, charge on-demand sur fichiers client/API vmlx.
paths:
  - "**/*vmlx*client*"
  - "**/*vmlx*api*"
  - "**/*vmlx*server*"
  - "**/openclaw.json"
  - "~/.openclaw/**"
---

# vMLX — Référence API complète

> Sous-rule de `~/.claude/rules/vmlx.md` (overview + caching + JANG). Transféré du skill `intellisoins-mlx:vmlx` (`references/api_reference.md`) le 2026-05-24.

## Endpoints

Tous sur `http://localhost:8000` (port configurable via `--port`).

### POST /v1/chat/completions (OpenAI)

```json
{
  "model": "default",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "temperature": 0.7,
  "max_tokens": 1024,
  "stream": false,
  "tools": [...],
  "tool_choice": "auto"
}
```

#### Nemotron-Omni multimodal (v1.4.0+) — image + audio + video

```python
# Bundle Nemotron-Omni servi avec --omni-backend stage1 (default) ou stage2
response = client.chat.completions.create(
    model="default",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
            {"type": "input_audio", "input_audio": {"data": "<base64>", "format": "wav"}}
        ]
    }]
)
```

Le content type `video_url` est aussi supporté pour Nemotron-Omni (mêmes formats que `image_url` : `file://`, `data:`, URL HTTP). Nécessite un bundle Nemotron-Omni servi avec `--omni-backend stage1` (default, bit-exact PyTorch+MPS) ou `--omni-backend stage2` (~17× faster RADIO + ~15× faster Parakeet, MLX natif, quality gaps documentées en validation upstream).

### POST /v1/messages (Anthropic)

```python
import anthropic
client = anthropic.Anthropic(base_url="http://localhost:8000", api_key="local")

message = client.messages.create(
    model="default",
    max_tokens=1024,
    system="Tu es un assistant médical.",
    messages=[{"role": "user", "content": "Quelles sont les interactions du lopinavir?"}]
)
print(message.content[0].text)
```

Avantage: code compatible Claude API → peut pointer vers vMLX local sans modification.

### POST /v1/embeddings

```python
response = client.embeddings.create(
    model="default",
    input=["Texte à encoder", "Autre texte"]
)
vectors = [e.embedding for e in response.data]
```

### POST /v1/rerank (cross-encoder reranking)

```bash
curl http://localhost:8000/v1/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "model": "local",
    "query": "Qu est-ce que le machine learning?",
    "documents": [
      "Le ML est un sous-ensemble de l IA",
      "La météo est ensoleillée aujourd hui",
      "Les réseaux de neurones apprennent des données"
    ]
  }'
```

Retourne un score de pertinence par document. Utile pour réordonner des résultats pgvector top-50 avant top-10 final (pipeline BGE Reranker v2-m3).

### POST /v1/responses (OpenAI Responses API)

Format streaming alternatif compatible OpenAI Responses.

**Nemotron-Omni via content types canoniques** (v1.4.2+) — `input_image` / `input_audio` / `input_video` sont auto-normalisés vers les envelopes chat-completions correspondants (`image_url` / `input_audio` / `video_url`), donc le même bundle Nemotron-Omni répond aux deux surfaces sans config additionnelle :

```python
response = client.responses.create(
    model="default",
    input=[{
        "role": "user",
        "content": [
            {"type": "input_text", "text": "Décris l'image et transcris l'audio."},
            {"type": "input_image", "image_url": "data:image/jpeg;base64,..."},
            {"type": "input_audio", "audio": {"data": "<base64>", "format": "wav"}},
            {"type": "input_video", "video_url": "file:///chemin/clip.mp4"}
        ]
    }]
)
```

### Endpoints cluster (multi-Mac distributed)

- `GET /v1/cluster/status` — état du cluster, coordinator, workers actifs
- `GET /v1/cluster/nodes` — liste nodes découverts (link type, latency, layer range)
- `POST /v1/cluster/scan` — force redécouverte des peers

### Cache stats et health

- `GET /v1/cache/stats` — statistiques L1/L2, hit rate, tokens cachés
- `GET /health` — health check serveur
- `GET /v1/models` — liste des modèles chargés

### POST /v1/audio/speech (Kokoro TTS)

```python
response = client.audio.speech.create(
    model="kokoro",
    input="Texte à lire",
    voice="default"  # Kokoro expose plusieurs voix
)
response.stream_to_file("output.mp3")
```

Installation requise: `pip install "vmlx[audio]"`.

### POST /v1/audio/transcriptions (Whisper STT)

```python
with open("audio.mp3", "rb") as f:
    transcript = client.audio.transcriptions.create(
        model="whisper",
        file=f
    )
print(transcript.text)
```

### POST /v1/images/generations (Flux / Z-Image / Qwen-Image)

```python
response = client.images.generate(
    model="schnell",  # ou "dev", "z-image-turbo", "qwen-image"
    prompt="Une pharmacie communautaire québécoise moderne, rendu photoréaliste",
    n=1,
    size="1024x1024"
)
print(response.data[0].url)  # ou .b64_json selon config
```

**Modèles de génération:**

| Modèle            | Steps | Vitesse     | Mémoire  |
| ----------------- | ----- | ----------- | -------- |
| **Flux Schnell**  | 4     | Plus rapide | ~6-24 GB |
| **Z-Image Turbo** | 4     | Rapide      | ~6-24 GB |
| **Flux Dev**      | 20    | Lent        | ~6-24 GB |

Installation requise: `pip install "vmlx[image]"`.

### POST /v1/images/edits (Qwen Image Edit — instruction-based)

```python
with open("photo.png", "rb") as img:
    response = client.images.edit(
        model="qwen-image-edit",
        image=img,
        prompt="Ajouter un comptoir de conseil pharmaceutique",
        n=1
    )
```

Modèle: **Qwen Image Edit** (28 steps, ~54 GB, full precision only). Lancer avec `vmlx serve qwen-image-edit`.

### Format Ollama (`/api/chat`, `/api/generate`)

vMLX répond aussi au wire format Ollama — utile pour les clients existants (Open WebUI,
continuedev en mode Ollama) sans changer de config:

```bash
curl http://localhost:8000/api/chat -d '{
  "model": "default",
  "messages": [{"role": "user", "content": "Bonjour"}],
  "stream": false
}'
```

## Commandes CLI

```bash
vmlx serve <model>              # Démarrer le serveur d inférence
vmlx convert <model> --bits 4   # Quantization MLX uniforme
vmlx convert <model> -j JANG_3M # Quantization JANG adaptive
vmlx info <model>               # Métadonnées et config du modèle
vmlx doctor <model>             # Diagnostics
vmlx bench <model>              # Benchmarks de performance
vmlx-worker --secret <secret>   # Démarrer un worker distribué
```

### Options serveur (vmlx serve)

```
vmlx serve <MODEL> [OPTIONS]

  <MODEL>                        HuggingFace ID ou chemin local (positionnel)
  --host TEXT                    Adresse de bind (défaut: 0.0.0.0)
  --port INT                     Port (défaut: 8000)
  --api-key TEXT                 Clé API optionnelle
  --continuous-batching          Active le batching continu
  --enable-prefix-cache          Réutilise les KV states pour prompts répétés
  --use-paged-cache              Paged KV cache avec dedup content-addressable
  --kv-cache-quantization [q4|q8]  Quantization du cache KV
  --enable-disk-cache            Persiste le cache sur SSD
  --enable-jit                   JIT compilation Metal kernels (expérimental)
  --tool-call-parser TEXT        Parser tool calls (défaut: auto)
  --reasoning-parser TEXT        Parser reasoning/thinking (défaut: auto)
  --log-level [DEBUG|INFO|WARNING|ERROR]
  --max-model-len INT            Contexte max
  --speculative-model TEXT       Draft model pour speculative decoding
  --enable-pld                   Prompt Lookup Decoding (pas de draft, code/JSON)
  --distributed                  Pipeline parallelism multi-Mac
  --cluster-secret TEXT          Shared secret pour workers
  --distributed-mode [pipeline|tensor]  pipeline (défaut)
  --worker-nodes TEXT            IPs manuelles workers (override auto-discovery)
  --smelt                        Smelt mode pour MoE (chargement partiel experts)
  --smelt-experts INT            Pourcentage d experts à charger (défaut: 50)
  --omni-backend [stage1|stage2] Encoder backend Nemotron-Omni (v1.4.7+).
                                 stage1 (default): PyTorch+MPS bit-exact reference.
                                 stage2: MLX natif, ~17× RADIO + ~15× Parakeet.
                                 Équivalent env var: VMLX_OMNI_BACKEND=stage2
  --cors-origins TEXT            CORS allowed origins (défaut: *)
```

### Options conversion (vmlx convert)

```
vmlx convert <MODEL> [OPTIONS]

  --bits [2|3|4|6|8]             Bits pour quantization uniforme
  --group-size INT               Group size quantization (défaut: 64)
  --output PATH                  Dossier de sortie
  --jang-profile [JANG_2M|JANG_2L|JANG_3M|JANG_4M|JANG_6M]
  --calibration-method [activations]  Calibration activation-aware (meilleur à 2-3 bit)
```

## Speculative Decoding

Accélère la génération avec un modèle draft plus petit:

```bash
vmlx serve mlx-community/Qwen3-8B-4bit \
  --speculative-model mlx-community/Qwen3-0.6B-4bit
```

Le modèle draft génère des tokens candidats, le modèle principal valide en batch.
Gain typique: 1.5-2× sur les tokens fréquents.

## Prompt Lookup Decoding (PLD)

Alternative sans draft model — cherche les n-grams répétés du prompt comme candidats:

```bash
vmlx serve mlx-community/Qwen3-8B-4bit --enable-pld
```

Gain 20-90% sur code editing, JSON, schemas où l'output cite l'input. Se combine avec les caches.

## Distributed Inference (multi-Mac)

```bash
# Sur les workers (chaque Mac):
vmlx-worker --secret mysecret

# Sur le coordinator (lance le serveur):
vmlx serve JANGQ-AI/Qwen3.5-Coder-Rerank-397B-A27B-JANG_2L \
  --distributed \
  --cluster-secret mysecret \
  --distributed-mode pipeline
```

Auto-discovery: Bonjour mDNS, UDP broadcast, Tailscale, cached peers. Network: TB5, 10GbE, WiFi — PP n'est pas bandwidth-bound.

## Vision-Language Models

```python
response = client.chat.completions.create(
    model="default",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Que vois-tu sur cette image?"},
            {"type": "image_url", "image_url": {"url": "file:///chemin/image.jpg"}}
        ]
    }]
)
```

Formats image supportés: `file://`, `data:image/...;base64,...`, URLs HTTP.

VLMs supportés: Qwen-VL, Qwen3.5-VL, Pixtral, InternVL, LLaVA, Gemma 3n.

## Agentic Tools intégrés (20+)

Appeler directement sans configuration MCP:

```python
tools = [
    {"type": "function", "function": {"name": "read_file", ...}},
    {"type": "function", "function": {"name": "execute_shell", ...}},
    {"type": "function", "function": {"name": "web_search", ...}},
]
```

Tools disponibles: `read_file`, `write_file`, `list_directory`, `execute_shell`,
`git_status`, `git_commit`, `web_search`, `clipboard_read`, `clipboard_write`, et plus.

## Intégration avec OpenClaw

Configurer comme provider dans `~/.openclaw/openclaw.json`:

```json
{
  "providers": {
    "vmlx-local": {
      "baseUrl": "http://127.0.0.1:8000/v1",
      "apiKey": "local",
      "api": "openai-completions",
      "models": [
        {
          "id": "default",
          "name": "vMLX Local",
          "reasoning": true,
          "contextWindow": 131072,
          "maxTokens": 8192,
          "input": ["text"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
        }
      ],
      "compat": {
        "supportedParameters": ["tools", "tool_choice"]
      }
    }
  }
}
```

**Important**: `compat.supportedParameters` est obligatoire pour OpenClaw (issue #15702).

## Troubleshooting

**Modèle non trouvé**: `huggingface-cli download mlx-community/<model>`

**Out of memory**: Activer `--kv-quant q4` ou choisir un modèle plus petit.

**Port occupé**: `lsof -i :8000` pour identifier le processus, puis `--port 8001`.

**Conflit vllm-mlx**: Les deux projets utilisent le port 8000 par défaut.
Utiliser `--port 8001` pour l'un des deux.
