---
description: Carte de la stack MLX locale (Apple Silicon) — frameworks d'inférence/lib Apple, 8 serveurs d'inférence, fine-tuning, optimisation KV. Index qui pointe vers les rules détaillées + skills intellisoins-mlx, versions upstream au 2026-05-29. Charge on-demand sur fichiers MLX, servers.yaml ou stack ai-servers.
paths:
  - "~/ai-servers/**"
  - "**/servers.yaml"
  - "**/*mlx*"
  - "**/*vllm*"
---

# Carte de la stack MLX locale (rule-index on-demand)

> **Rôle** : carte d'orientation de la stack MLX sur Apple Silicon — elle **pointe** vers les rules détaillées (`~/.claude/rules/*.md`) et les skills `intellisoins-mlx:*`, jamais ne duplique leur contenu. Versions upstream relevées au **2026-05-29** (voir Citations en bas). Pour le setup d'ensemble de la stack locale, voir `~/.claude/rules/local-ai-stack.md`.
> **Lecture des colonnes** : `version` = dernier tag/release stable au 2026-05-29 ; `⬆` = bump constaté depuis la dernière note connue ; le pointeur final est une **rule** si elle existe, sinon un **skill** `intellisoins-mlx:`.

## A. Frameworks d'inférence & lib Apple (skills)

| Framework      | repo                   | version @2026-05-29              | rôle                               | skill                             |
| -------------- | ---------------------- | -------------------------------- | ---------------------------------- | --------------------------------- |
| mlx-lm         | ml-explore/mlx-lm      | v0.31.3 (2026-04-22)             | inférence LLM core                 | `intellisoins-mlx:mlx`            |
| mlx-vlm        | Blaizzy/mlx-vlm        | **v0.5.0** (2026-05-06, ⬆ 0.4.4) | VLM image/audio/vidéo              | `intellisoins-mlx:mlx-vlm`        |
| mlx-embeddings | Blaizzy/mlx-embeddings | v0.1.0 (2026-03-24, stable)      | embeddings + reranking             | `intellisoins-mlx:mlx-embeddings` |
| mlx (core)     | ml-explore/mlx         | v0.31.2 (2026-04-22)             | framework array/NN de base         | `intellisoins-mlx:mlx-dev`        |
| mflux          | filipstrand/mflux      | v0.17.5 (2026-04-10, stable)     | image-gen (Flux/Z-Image/Qwen/FIBO) | `intellisoins-mlx:mflux`          |

## B. Serveurs d'inférence — AVEC rule dédiée

| Serveur           | repo                       | version @2026-05-29                                   | rôle                                              | rule + skill                                                                   |
| ----------------- | -------------------------- | ----------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------ |
| vmlx              | jjang-ai/vmlx              | **v1.5.49** (2026-05-24, ⬆ 1.5.0) + v2.0.0-rc.1 Swift | engine multi-modèle, 5-layer KV, JANG             | `~/.claude/rules/vmlx.md` (+ `vmlx/`) · `intellisoins-mlx:vmlx`                |
| vllm-mlx          | waybarrios/vllm-mlx        | **v0.3.0** (2026-05-09, ⬆ 0.2.9) + v0.4.0rc1          | OpenAI+Anthropic, continuous batching, rerank     | `~/.claude/rules/vllm-mlx.md` (+ `vllm-mlx/`) · `intellisoins-mlx:vllm-mlx`    |
| vllm-metal        | vllm-project/vllm-metal    | rolling daily (v0.2.0-20260528)                       | plugin Metal officiel vLLM                        | `~/.claude/rules/vllm-metal.md` · `intellisoins-mlx:vllm-metal`                |
| vllm-omni         | vllm-project/vllm-omni     | **v0.20.0** (2026-05-07) + v0.21.0rc1                 | ⚠️ GPU CUDA/ROCm, PAS Apple Silicon               | `~/.claude/rules/vllm-omni.md` (+ `vllm-omni/`) · `intellisoins-mlx:vllm-omni` |
| omlx              | jundot/omlx                | **v0.3.12** (2026-05-27, ⬆ 0.3.9rc1)                  | tiered KV cache SSD, backend Claude Code, menubar | `~/.claude/rules/omlx.md`                                                      |
| mlx-omni-server   | madroidmaq/mlx-omni-server | **v0.5.3** (2026-05-09)                               | dual API OpenAI+Anthropic, zero-config            | `~/.claude/rules/mlx-omni-server.md`                                           |
| mlx-openai-server | cubist38/mlx-openai-server | **v1.8.1** (2026-05-03)                               | multi-model YAML, LoRA hot-load, FLUX             | `~/.claude/rules/mlx-openai-server.md`                                         |

> ⚠️ Fork `Blaizzy/vllm-omni` = MORT (dernier push 2026-02-01, aucun tag) — utiliser `vllm-project/vllm-omni`.

> Les 3 restants (omlx, mlx-omni-server, mlx-openai-server) ont été migrés du plugin `intellisoins-mlx` vers ces rules le 2026-05-29 ; leurs skills sources sont en staging `~/.claude/plugins-staging/mlx-servers/` (désactivés, réversibles).

> Hub de comparaison des 8 serveurs : skill `intellisoins-mlx:mlx-inference-servers`.

## C. Optimisation KV

| Outil          | repo                       | version @2026-05-29                            | rôle                      | rule + skill                                                            |
| -------------- | -------------------------- | ---------------------------------------------- | ------------------------- | ----------------------------------------------------------------------- |
| turboquant-mlx | helgklaizar/turboquant-mlx | pas de tag, dernier commit 2026-04-10 (stable) | compression KV-cache 3-5× | `~/.claude/rules/turboquant-mlx.md` · `intellisoins-mlx:turboquant-mlx` |

## D. Fine-tuning (pointeurs skills, pas de version)

Skills `intellisoins-mlx:` — `mlx-fine-tuning`, `mlx-vlm-fine-tuning`, `mlx-tune` (ARahim3/mlx-tune **v0.5.0**, 2026-05-19), `gemma3-finetune`, `gemma4-mlx`, `medgemma-finetune`, `medgemma-prompting`, `nemotron-finetune`, `qwen3-finetuning-tool-calling`, `qwen35-vision-finetuning`, `gliner-ner`, `bert-relation-extraction`.

## E. Audio / Vision / Vidéo / Swift / Éval (pointeurs skills)

Skills `intellisoins-mlx:` — `mlx-audio`, `mlx-audio-swift`, `parakeet-mlx`, `mlx-video`, `ui-tars-mlx`, `mlx-swift-lm`, `on-device-ai`, `onnx`, `mlx-bitnet`, `mlx-evaluation`, `mlx-classifier`, `sentence-transformers`, `mlx-dev`.

## Connexes

- `~/.claude/rules/local-ai-stack.md` — setup d'ensemble de la stack locale.
- `~/.claude/rules/training-datasets.md` — datasets de fine-tuning.

## Cross-références

- `~/.claude/rules/rules-index.md` — catalogue global des rules ; cette carte le **complète côté skills** `intellisoins-mlx:` (que l'index ne détaille pas).
- ⚠️ Les rules serveurs détaillées (`vmlx.md`, `vllm-*.md`, `turboquant-mlx.md`) peuvent être légèrement **datées** vs la colonne `version` ci-dessus (drift connu au 2026-05-29) — se fier à la version de cette carte pour le tag courant, à la rule pour le détail de configuration.

## Citations

<citation>https://pypi.org/project/mlx-lm/ — consulté 2026-05-29, release 2026-04-22</citation>
<citation>https://pypi.org/project/mlx-vlm/ — consulté 2026-05-29, release 2026-05-06</citation>
<citation>https://pypi.org/project/mlx-embeddings/ — consulté 2026-05-29, release 2026-03-24</citation>
<citation>https://pypi.org/project/mlx/ — consulté 2026-05-29, release 2026-04-22</citation>
<citation>https://pypi.org/project/mflux/ — consulté 2026-05-29, release 2026-04-10</citation>
<citation>https://github.com/ARahim3/mlx-tune/releases — consulté 2026-05-29, release 2026-05-19</citation>
<citation>https://api.github.com/repos/jjang-ai/vmlx/releases — consulté 2026-05-29, release 2026-05-24</citation>
<citation>https://api.github.com/repos/jundot/omlx/releases — consulté 2026-05-29, release 2026-05-27</citation>
<citation>https://api.github.com/repos/waybarrios/vllm-mlx/releases — consulté 2026-05-29, release 2026-05-09</citation>
<citation>https://api.github.com/repos/vllm-project/vllm-metal/releases — consulté 2026-05-29, release 2026-05-28</citation>
<citation>https://api.github.com/repos/vllm-project/vllm-omni/releases — consulté 2026-05-29, release 2026-05-07</citation>
<citation>https://api.github.com/repos/madroidmaq/mlx-omni-server/releases — consulté 2026-05-29, release 2026-05-09</citation>
<citation>https://api.github.com/repos/cubist38/mlx-openai-server/releases — consulté 2026-05-29, release 2026-05-03</citation>
<citation>https://api.github.com/repos/ollama/ollama/releases/latest — consulté 2026-05-29, release 2026-05-14</citation>
<citation>https://api.github.com/repos/helgklaizar/turboquant-mlx/commits — consulté 2026-05-29, dernier commit 2026-04-10 (aucun tag)</citation>
