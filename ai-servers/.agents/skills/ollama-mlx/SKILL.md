---
name: ollama-mlx

description: ollama-mlx — runner MLX natif d'Ollama sur Apple Silicon : format safetensors, KV cache avec snapshots, quantization nvfp4, support Gemma 4, import de modèles MLX HuggingFace, benchmarking, backend Claude Code local. Charge on-demand sur fichiers ollama ou servers.yaml.
paths:
  - "**/*ollama*"
  - "**/servers.yaml"
---

# Ollama — Runner MLX natif (Apple Silicon)

Depuis la v0.19.0, Ollama sur Apple Silicon utilise nativement le framework MLX d'Apple au lieu de GGUF/llama.cpp. Ça active le format safetensors, les snapshots de KV cache, et la quantization nvfp4 — refermant l'écart de performance avec l'inférence directe mlx-lm.

Version courante : **Ollama v0.24.0 (2026-05-14)**. Le **runner MLX lui-même est inchangé** depuis la série v0.20.x — les releases récentes (v0.21–v0.24) sont app-focused (UI, intégrations, fixes), pas des changements du backend d'inférence MLX. Les caractéristiques techniques ci-dessous (architectures supportées, KV cache, nvfp4, import) restent valides.

## Ce qui a changé en v0.19.0 → v0.20.x (bascule MLX)

| Avant (GGUF)                                | Après (MLX natif)                          |
| ------------------------------------------- | ------------------------------------------ |
| Modèles stockés en blobs GGUF monolithiques | Modèles stockés en safetensors individuels |
| Backend llama.cpp                           | Backend MLX C API                          |
| Pas de persistance KV cache                 | Snapshots de KV cache entre les requêtes   |
| Quantization Q4_K_M, Q8_0                   | nvfp4 + int4/int8 standard                 |
| Agnostique à l'architecture (GGUF)          | Runner MLX spécifique à l'architecture     |

Le runner MLX est identifié par `"model_format": "safetensors"` dans la config du modèle. Les modèles GGUF fonctionnent toujours — Ollama retombe sur le runner llama.cpp pour ceux-là.

### Jalons techniques de la série v0.20.x (avril 2026, où le runner MLX a pris sa forme actuelle)

- **v0.20.0** — modèles Gemma 4 (e2b, e4b, 26b MoE, 31b dense) + tokenizer BPE style SentencePiece + fix du pipeline MLX pour `add_bos_token`
- **v0.20.4** — améliorations de perf MLX pour puces M5 (Neural Accelerators), flash attention pour Gemma 4
- **v0.20.5** — setup du canal `ollama launch openclaw`, fix de la commande `/save` pour les imports safetensors
- **v0.20.6** — meilleur tool calling Gemma 4, tool calling parallèle dans les réponses en streaming
- **v0.20.7** — fix qualité gemma:e2b/e4b quand le thinking est désactivé, ROCm 7.2.1 (Linux)

## Architectures supportées

Le runner MLX supporte ces familles de modèles (source : `x/mlxrunner/imports.go`) :

| Architecture    | Modèles                                | Import ID       |
| --------------- | -------------------------------------- | --------------- |
| `llama`         | Llama 3.x, Mistral, Phi, CodeLlama     | `llama`         |
| `gemma3`        | Gemma 3                                | `gemma3`        |
| `gemma4`        | Gemma 4 (e2b, e4b, 26b MoE, 31b dense) | `gemma4`        |
| `qwen3`         | Qwen3 (dense)                          | `qwen3`         |
| `qwen3_5`       | Qwen3.5 (dense, 9.7B)                  | `qwen3_5`       |
| `qwen3_5_moe`   | Qwen3.5 MoE (35B-A3B)                  | `qwen3_5_moe`   |
| `glm4_moe_lite` | GLM-4 MoE Lite                         | `glm4_moe_lite` |

Les modèles hors de cette liste (DeepSeek, Cohere, Phi-4) retombent sur GGUF/llama.cpp. La liste grandit à chaque release Ollama.

### Lancer Gemma 4 (v0.20.0+)

```bash
# Effective 2B — le plus rapide, bon pour tool calling / réponses courtes
ollama run gemma4:e2b

# Effective 4B — équilibre qualité/vitesse
ollama run gemma4:e4b

# 26B MoE (4B actifs) — meilleur raisonnement à latence raisonnable
ollama run gemma4:26b

# 31B dense — qualité maximale
ollama run gemma4:31b
```

Le tool calling fonctionne nativement, y compris en mode streaming (v0.20.6+). Flash attention est activé automatiquement sur les GPU compatibles (v0.20.4+).

## KV cache et prompt caching

Le runner MLX d'Ollama maintient des snapshots de KV cache entre les requêtes. Le cache stocke les états d'attention calculés pour les préfixes de prompt, évitant le recalcul quand des requêtes subséquentes partagent le même préfixe.

### Quand le cache aide

- Conversations chat multi-tours (system prompt + historique réutilisés)
- Inférence Claude Code local (gros system prompt réutilisé à chaque requête)
- RAG avec documents de contexte fixes
- Appels API répétés avec instructions système partagées

### Performance mesurée (M3 Max 128GB, Qwen3.5-35B-A3B)

| Requête                    | Tokens prompt | Vitesse prompt | Effet cache  |
| -------------------------- | ------------- | -------------- | ------------ |
| Tour 1 (froid)             | 58            | 368 t/s        | Pas de cache |
| Tour 2 (même préfixe)      | 77            | 824 t/s        | 2.2x speedup |
| Tour 3 (préfixe plus long) | 95            | 1 027 t/s      | 2.8x speedup |
| Nouvelle conversation      | 31            | 308 t/s        | Pas de cache |

La vitesse de génération reste constante (~87 t/s) — le cache n'accélère que le traitement du prompt.

### Tester le cache

Utiliser l'endpoint `/api/chat` avec des messages multi-tours pour déclencher le caching de préfixe :

```python
import requests

URL = "http://localhost:11434/api/chat"
MODEL = "qwen3.5:35b-a3b-coding-nvfp4"

# Tour 1 — froid
msgs = [
    {"role": "system", "content": "Your long system prompt here"},
    {"role": "user", "content": "First question"}
]
r1 = requests.post(URL, json={"model": MODEL, "messages": msgs, "stream": False})
d1 = r1.json()

# Tour 2 — préfixe caché (system + tour 1 réutilisés)
msgs.append({"role": "assistant", "content": d1["message"]["content"]})
msgs.append({"role": "user", "content": "Follow-up question"})
r2 = requests.post(URL, json={"model": MODEL, "messages": msgs, "stream": False})
d2 = r2.json()

# Comparer prompt_eval_duration entre d1 et d2
```

### KV cache Ollama vs MLX direct

| Métrique              | Ollama (MLX runner)                           | mlx-lm (prompt_cache)                              |
| --------------------- | --------------------------------------------- | -------------------------------------------------- |
| Mécanisme de cache    | Automatique entre requêtes API                | Manuel via `save_prompt_cache`/`load_prompt_cache` |
| Vitesse prompt tour 3 | 1 027 t/s                                     | 1 005 t/s                                          |
| Requiert du code      | Non (transparent)                             | Oui (gestion explicite du fichier cache)           |
| Persistance           | En mémoire (perdue au déchargement du modèle) | Sur fichier (`.safetensors`)                       |

## Performance : Ollama MLX vs mlx-lm direct

Benchmarké sur M3 Max 128GB avec Qwen3.5-35B-A3B-4bit :

| Métrique           | Ollama (nvfp4) | mlx-lm direct (4-bit) | Delta       |
| ------------------ | -------------- | --------------------- | ----------- |
| **Génération**     | 87 t/s         | 106 t/s               | mlx-lm +22% |
| **Prompt (froid)** | 291 t/s        | 431 t/s               | mlx-lm +48% |
| **Mémoire pic**    | ~21 GB         | 19.6 GB               | mlx-lm -7%  |

Le surcoût de ~20% en génération vient du serveur HTTP d'Ollama, de la gestion de session et du scheduling. Pour le batch ou le débit maximal, mlx-lm direct gagne. Pour la commodité, la compatibilité API et le KV caching automatique, Ollama gagne.

## Importer des modèles safetensors locaux

Importer n'importe quel modèle au format MLX depuis le cache HuggingFace ou un répertoire local :

```bash
# Créer un Modelfile pointant vers les safetensors locaux
echo "FROM /path/to/model/directory" > Modelfile

# Importer avec le flag --experimental
ollama create my-model --experimental -f Modelfile

# Vérifier
ollama show my-model --verbose
```

Le répertoire du modèle doit contenir `config.json`, `tokenizer.json` et les fichiers de poids `.safetensors` — le layout standard HuggingFace/MLX.

### Import depuis le cache HuggingFace

```bash
# Trouver le chemin du snapshot du modèle
ls ~/.cache/huggingface/hub/models--mlx-community--Qwen3.5-35B-A3B-4bit/snapshots/

# Créer le Modelfile
echo "FROM ~/.cache/huggingface/hub/models--mlx-community--Qwen3.5-35B-A3B-4bit/snapshots/<hash>" > Modelfile

# Importer
ollama create qwen35-local --experimental -f Modelfile
```

### Import de modèles MLX fine-tunés

C'est le pipeline clé pour déployer des modèles fine-tunés via Ollama :

```bash
# 1. Fine-tune avec mlx-lm
python3 -m mlx_lm lora --model mlx-community/Qwen3-8B-4bit \
    --train --data ./data --adapter-path ./adapters

# 2. Fuser l'adapter dans le modèle
python3 -m mlx_lm fuse --model mlx-community/Qwen3-8B-4bit \
    --adapter-path ./adapters --save-path ./fused-model

# 3. Importer directement dans Ollama (aucune conversion GGUF nécessaire)
echo "FROM ./fused-model" > Modelfile
ollama create my-finetuned --experimental -f Modelfile

# 4. Utiliser
ollama run my-finetuned "Your prompt"
```

Ça contourne entièrement la conversion GGUF, préservant le format de poids MLX original. Le modèle tourne sur le runner MLX natif avec support du KV cache.

Contrainte d'architecture : l'architecture du modèle fusé doit figurer dans la liste supportée (llama, gemma3, qwen3, qwen3_5, qwen3_5_moe, glm4_moe_lite).

Pour les architectures non supportées, utiliser le fallback GGUF :

```bash
python3 -m mlx_lm fuse --model <base> --adapter-path ./adapters --export-gguf
echo "FROM ./ggml-model-f16.gguf" > Modelfile
ollama create my-model -f Modelfile
```

## Variables d'environnement

| Variable                   | Défaut            | Description                                        |
| -------------------------- | ----------------- | -------------------------------------------------- |
| `OLLAMA_HOST`              | `127.0.0.1:11434` | Adresse du serveur                                 |
| `OLLAMA_KV_CACHE_TYPE`     | `f16`             | Quantization du KV cache (f16, q8_0, q4_0)         |
| `OLLAMA_FLASH_ATTENTION`   | off               | Activer flash attention                            |
| `OLLAMA_KEEP_ALIVE`        | `5m`              | Durée pendant laquelle les modèles restent chargés |
| `OLLAMA_CONTEXT_LENGTH`    | auto              | Override de la longueur de contexte                |
| `OLLAMA_MAX_LOADED_MODELS` | 1                 | Modèles concurrents maximum                        |

### Quantization du KV cache

Réduire la mémoire pour les longs contextes :

```bash
# q8_0 KV cache — réduction ~50% mémoire, perte de qualité minimale
OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve

# q4_0 KV cache — réduction ~75%, perte de qualité sur longs contextes
OLLAMA_KV_CACHE_TYPE=q4_0 ollama serve
```

## Script de benchmark

Benchmark rapide pour comparer des modèles Ollama ou mesurer les effets du cache :

```python
import requests, json, time

def bench(model, messages, label, num_predict=100):
    r = requests.post("http://localhost:11434/api/chat", json={
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": num_predict}
    })
    d = r.json()
    pt = d.get("prompt_eval_count", 0)
    pd = d.get("prompt_eval_duration", 1) / 1e9
    et = d.get("eval_count", 0)
    ed = d.get("eval_duration", 1) / 1e9
    print(f"{label}")
    print(f"  Prompt: {pt} tok in {pd:.3f}s = {pt/pd:.0f} t/s")
    print(f"  Gen:    {et} tok in {ed:.3f}s = {et/ed:.1f} t/s")
    return d["message"]["content"]
```

## Inférence Claude Code local

Faire tourner le CLI Claude Code contre Ollama MLX au lieu de l'API Anthropic.

### Démarrage rapide

```bash
# Raccourci — configure auth + base URL automatiquement
ollama launch claude --model qwen3.5:35b-a3b-coding-nvfp4

# Ou manuel — les 3 env vars requises ensemble
ANTHROPIC_AUTH_TOKEN=ollama \
ANTHROPIC_API_KEY="" \
ANTHROPIC_BASE_URL=http://localhost:11434 \
claude --model qwen3.5:35b-a3b-coding-nvfp4
```

### Bypass d'auth (pourquoi 3 env vars)

| Variable                                    | Valeur                | Rôle                                                      |
| ------------------------------------------- | --------------------- | --------------------------------------------------------- |
| `ANTHROPIC_AUTH_TOKEN=ollama`               | Toute chaîne non vide | Satisfait le check d'auth de Claude Code                  |
| `ANTHROPIC_API_KEY=""`                      | Chaîne vide           | Empêche la vraie clé API du `.zshrc` de prendre le dessus |
| `ANTHROPIC_BASE_URL=http://localhost:11434` | Endpoint Ollama       | Redirige les requêtes vers le serveur local               |

Si une vraie `ANTHROPIC_API_KEY` existe dans `.zshrc`/`.zprofile`, l'override inline vide est obligatoire — Claude Code priorise les vraies clés sur `ANTHROPIC_BASE_URL`.

Si le bypass d'auth échoue encore, vérifier :

- `~/.claude.json` — retirer le champ `oauthAccount` (état de login Max/Pro)
- macOS Keychain — supprimer l'entrée "Claude Safe Storage"
- Lancer `/logout` dans Claude Code d'abord, puis relancer avec les env vars

### Alias shell

```bash
# Ajouter à ~/.zshrc
alias claude-local='ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_API_KEY="" ANTHROPIC_BASE_URL=http://localhost:11434 claude --model qwen3.5:35b-a3b-coding-nvfp4'
```

### Mode non-interactif (scripts, CI)

```bash
ollama launch claude --model qwen3.5:35b-a3b-coding-nvfp4 --yes -- -p "how does this repo work?"
```

### Pourquoi Ollama MLX pour Claude Code

- **KV cache automatique** — le gros system prompt de Claude Code (~10K+ tokens) est caché entre les requêtes, donnant un speedup de 2-3x sur le traitement du prompt après le premier tour
- **Pas de proxy nécessaire** — Ollama 0.19+ expose `/v1/messages` nativement en format Anthropic
- **Modèle reste chargé** — `OLLAMA_KEEP_ALIVE=30m` garde le modèle au chaud entre requêtes
- **Tool calling fonctionne** — Ollama gère tool_use/tool_result en format de message Anthropic

### Limitations vs API Anthropic

| Fonctionnalité             | Ollama MLX                            | API Anthropic             |
| -------------------------- | ------------------------------------- | ------------------------- |
| Texte + streaming          | Oui                                   | Oui                       |
| Tool calling               | Oui                                   | Oui                       |
| Extended thinking          | Non                                   | Oui                       |
| Prompt caching (explicite) | Non (KV cache automatique à la place) | Oui (blocs cache_control) |
| Web search                 | Non                                   | Oui                       |
| Contexte max               | 256K (Qwen3.5)                        | 200K–1M (Claude)          |

### Performance du blog officiel Ollama (mars 2026)

| Métrique | Ollama 0.18 (GGUF) | Ollama 0.19 (MLX) | Ollama 0.19 (MLX nvfp4) |
| -------- | ------------------ | ----------------- | ----------------------- |
| Prefill  | 1 154 t/s          | 1 810 t/s         | 1 851 t/s               |
| Decode   | 58 t/s             | 112 t/s           | 134 t/s                 |

Les puces M5/M5 Pro/M5 Max exploitent les GPU Neural Accelerators pour un speedup additionnel. La v0.20.4 a ajouté d'autres améliorations de perf MLX ciblées spécifiquement sur les puces M5.

## Cross-références

- `mlx-inference-servers` (skill) — pour du serving MLX dédié (vllm-mlx, mlx-omni-server, mlx-openai-server). Ollama est plus simple mais moins configurable.
- `mlx-fine-tuning` (skill) — fine-tuner avec mlx-lm, puis importer dans Ollama via `--experimental`.
- `~/.claude/rules/litellm-providers-models.md` — utiliser Ollama comme backend pour l'inférence Claude Code local via le proxy LiteLLM.
- `ollama-mlx-fine-tuning` (skill) — pipeline end-to-end de fine-tuning MLX + déploiement Ollama via import safetensors natif.

<citation>https://api.github.com/repos/ollama/ollama/releases/latest — consulté 2026-05-29, release 2026-05-14</citation>
