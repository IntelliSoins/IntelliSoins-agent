---
description: vMLX — quantization JANG adaptive mixed-precision (bit widths variables par layer). 5 profils (JANG_2M/2L/3M/4M/6M), conversion de modèles, quand l'utiliser, tradeoffs, interaction avec 5-layer caching et Smelt mode (MoE). Sous-rule de ~/.claude/rules/vmlx.md.
paths:
  - "**/*jangq*"
  - "**/*JANG_*"
  - "**/*.jangq"
---

# JANG Adaptive Mixed-Precision Quantization

> Sous-rule de `~/.claude/rules/vmlx.md` (overview + API + caching). Transféré du skill `intellisoins-mlx:vmlx` (`references/jang_quantization.md`) le 2026-05-24.

JANG is a quantization format co-developed with vMLX by Jinho Jang.
Upstream runtime: [jjang-ai/jangq](https://github.com/jjang-ai/jangq) — "GGUF for MLX".
Modèles pré-quantifiés: [JANGQ-AI on HuggingFace](https://huggingface.co/JANGQ-AI).

## Why JANG exists

La quantization uniforme (MLX 4-bit, MLX 8-bit) traite chaque layer identiquement.
Certains layers tolèrent une compression agressive, d'autres font collapser le raisonnement du modèle.
JANG profile la sensibilité de chaque layer et assigne des bit widths en conséquence — attention préservée en haute précision, MLP compressé plus agressivement.

Le payoff empirique sur gros modèles est dramatique. Benchmark vedette **MiniMax M2.5 (200 questions MMLU)**:

| Quantization        | MMLU    | Size      |
| ------------------- | ------- | --------- |
| **JANG_2L (2-bit)** | **74%** | **89 GB** |
| MLX 4-bit           | 26.5%   | 120 GB    |
| MLX 3-bit           | 24.5%   | 93 GB     |
| MLX 2-bit           | 25%     | 68 GB     |

Le collapse de MLX 4-bit uniforme sur gros modèles est une pathologie connue — JANG la résout sans avoir besoin de 8-bit partout (qui gonfle la mémoire).

Scores détaillés: [jangq.ai](https://jangq.ai).

## Installation

```bash
pip install "vmlx[jang]"
```

Installe le runtime JANG_Q requis pour charger les weights JANG.

## Profils disponibles (5 profils)

| Profile   | Attention | Embeddings | MLP   | Avg Bits | Use Case             |
| --------- | --------- | ---------- | ----- | -------- | -------------------- |
| `JANG_2M` | 8-bit     | 4-bit      | 2-bit | ~2.5     | Compression balancée |
| `JANG_2L` | 8-bit     | 6-bit      | 2-bit | ~2.7     | Qualité en 2-bit     |
| `JANG_3M` | 8-bit     | 3-bit      | 3-bit | ~3.2     | **Recommandé**       |
| `JANG_4M` | 8-bit     | 4-bit      | 4-bit | ~4.2     | Qualité standard     |
| `JANG_6M` | 8-bit     | 6-bit      | 6-bit | ~6.2     | Near-lossless        |

Convention: `M` = MLP au même bit que l'embedding, `L` = MLP plus bas que l'embedding (variante "lower MLP" pour compression plus agressive).

## Utiliser des modèles JANG

```bash
vmlx serve JANGQ-AI/MiniMax-M2.5-JANG_2L
vmlx serve JANGQ-AI/Llama-3.3-70B-Instruct-JANG_3M
```

vMLX auto-détecte le format JANG depuis les weights et active le runtime JANG_Q.

## Convertir ses propres modèles

```bash
# Quantization MLX uniforme standard
vmlx convert my-model --bits 4

# Quantization JANG adaptive (profil recommandé)
vmlx convert my-model --jang-profile JANG_3M

# Calibration activation-aware (meilleur à 2-3 bit)
vmlx convert my-model --jang-profile JANG_2L --calibration-method activations

# Serve le modèle converti
vmlx serve ./my-model-JANG_3M --continuous-batching --use-paged-cache
```

Alternative: utiliser le CLI `jangq` depuis le [repo jangq](https://github.com/jjang-ai/jangq) pour les options avancées.

## Quand JANG est le bon choix

- **70B+ dense models sur 128 GB Macs** où 4-bit uniforme dégrade mal.
- **Gros MoE** (Qwen3.5-35B-A3B, Mixtral, MiniMax M2.5) où la précision sélective des experts compte.
- **Workflows agent qualité-sensibles** où les hallucinations 4-bit cascadent en mauvais tool calls.
- **Modèles à contraintes mémoire strictes** — JANG_2L sur M3 Ultra permet MiniMax M2.5 en 89 GB au lieu de 120.

Quand 4-bit uniforme performe déjà bien (petits modèles, workloads simples), JANG ajoute de la complexité sans gain de qualité significatif. Rester sur uniforme 4-bit ou 8-bit.

## Interaction avec le 5-layer caching

Les modèles JANG utilisent la stack complète de 5-layer KV cache sans changement. La quantization s'applique aux weights, pas au KV cache. On peut combiner `--kv-cache-quantization q8` avec un modèle JANG_2L pour efficacité mémoire maximale. Détail caching : `~/.claude/rules/vmlx/caching.md`.

## Interaction avec Smelt Mode (MoE)

Smelt charge un subset d'experts MoE depuis SSD — ne fonctionne **qu'avec des modèles JANG** (pas compatible avec dense ou non-JANG formats).

```bash
# Nemotron-Cascade-2-30B-A3B en JANG_4M avec 50% des experts
vmlx serve ./Nemotron-Cascade-2-30B-A3B-JANG_4M --smelt --smelt-experts 50
```

Benchmarks sur M3 Ultra 128 GB:

| `--smelt-experts` | Active RAM | Decode tok/s | RAM saving |
| ----------------- | ---------: | -----------: | ---------- |
| off (baseline)    |  17,408 MB |         89.9 | —          |
| 50                |   9,529 MB |         66.5 | -45%       |
| 25                |   5,590 MB |           \* | -68%       |

Output reste cohérent — le routing biasé garde le modèle on-topic.

**Note**: Smelt est mutuellement exclusif avec VLM mode (la vision tower n'est pas wirée dans le partial-expert loader).

## Tradeoffs à signaler

- **First-load plus lent** que quantization uniforme dû au per-layer bit unpacking.
- **Ecosystem plus étroit** que mlx-community mainstream quants — pas tous les fine-tunes disponibles en JANG.
- **JANG runtime footprint** fait partie de l'extra `[jang]` et augmente la taille d'install.
