---
description: vMLX — guide des 5 couches de KV caching (prefix, paged multi-context, quantization q4/q8, continuous batching, persistent disk L2 + block disk), configs recommandées par profil (agent/RAG/chat), métriques de performance. Sous-rule de ~/.claude/rules/vmlx.md.
paths:
  - "**/*vmlx*cache*"
  - "**/*kv*cache*"
  - "**/*prefix*cache*"
---

# vMLX — Guide de Caching

> Sous-rule de `~/.claude/rules/vmlx.md` (overview + API + JANG). Transféré du skill `intellisoins-mlx:vmlx` (`references/caching_guide.md`) le 2026-05-24.

## Les 5 couches expliquées

### 1. Prefix Caching

Réutilise les états KV calculés pour des prefixes identiques entre requêtes.

**Cas d'usage**: System prompt identique entre requêtes d'agents.

- Le system prompt est calculé une seule fois
- Les requêtes suivantes réutilisent le cache → TTFT quasi nul pour la partie cachée

```python
# Le system prompt sera mis en cache automatiquement
client.chat.completions.create(
    model="default",
    messages=[
        {"role": "system", "content": "Tu es un assistant médical..."},  # caché après 1ère req
        {"role": "user", "content": "Question variable"}
    ]
)
```

### 2. Paged Multi-Context KV Cache

Supporte jusqu'à 256 séquences concurrentes sans éviction.

**Différence clé vs LM Studio/Ollama**: Ces derniers invalident le cache quand le contexte
change (ex. switching de conversation). vMLX maintient le cache de chaque conversation
indépendamment via la gestion paginée.

```bash
# Activer via CLI
vmlx --max-num-seqs 256
```

### 3. KV Cache Quantization

Réduit l'empreinte mémoire du cache sans impact sur la précision de génération.

| Mode  | Économie mémoire | Quand utiliser                               |
| ----- | ---------------- | -------------------------------------------- |
| `q4`  | ~4×              | Contextes très longs (100K+), modèles larges |
| `q8`  | ~2×              | Bon compromis qualité/mémoire                |
| `f16` | 1× (défaut)      | Précision maximale                           |

```bash
# Activer q8 (recommandé pour agents longs)
vmlx --model mlx-community/Qwen3-4B-8bit --kv-quant q8
```

**Note**: La quantization s'applique au stockage du cache, pas à la génération —
la précision des tokens générés reste identique.

### 4. Continuous Batching

Traite plusieurs requêtes simultanément dans le même batch d'inférence.

```bash
vmlx --continuous-batching --max-num-seqs 256
```

Gain: 2-4× throughput agrégé à 16 requêtes concurrentes (vs séquentiel).

### 5. Persistent Disk Cache (L2)

Les états KV sont sauvegardés sur disque et récupérés après redémarrage du serveur.

- TTFT sur contextes longs (100K tokens): 131s (froid) → 0.05s (cache disque chaud)
- Particulièrement utile pour des sessions agents qui reprennent après interruption
- Flag: `--enable-disk-cache`

**Variante Block Disk Cache**: per-block persistent cache apparié au paged KV cache, activé automatiquement avec `--use-paged-cache --enable-disk-cache`. Granularité plus fine que le prompt-level cache — partage les blocks entre contextes qui se chevauchent partiellement.

## Configuration recommandée par profil

### Agent OpenClaw (sessions longues, contexte croissant)

```bash
vmlx \
  --model mlx-community/Qwen3.5-35B-A3B-4bit \
  --kv-quant q8 \
  --continuous-batching \
  --max-num-seqs 4
```

Pourquoi: kv-quant q8 permet de tenir plus de contexte en RAM; batching pour les
sous-agents parallèles d'OpenClaw (maxConcurrent: 2 agents, 4 subagents).

### RAG / Recherche (prefill lourd, output court)

```bash
vmlx \
  --model mlx-community/Qwen3-4B-8bit \
  --kv-quant q4 \
  --continuous-batching \
  --max-num-seqs 16
```

### Chat interactif (utilisateur unique)

```bash
vmlx --model mlx-community/Qwen3-8B-4bit
```

Aucune configuration spéciale — le prefix caching s'active automatiquement.

## Métriques de performance observées

| Contexte    | Sans cache   | Avec prefix cache   |
| ----------- | ------------ | ------------------- |
| 2.5K tokens | baseline     | 9.7× plus rapide    |
| 8K tokens   | ~49s prefill | ~1-2s prefill       |
| 100K tokens | 131s         | 0.65s (cache froid) |

Source: benchmarks vmlx.net (M3 Ultra 256GB, Llama-3.2-3B-Instruct-4bit).
Performances variables selon le modèle et le hardware.
