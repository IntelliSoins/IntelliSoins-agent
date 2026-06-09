---
name: training-datasets
description: Catalogue des datasets d'entrainement pour fine-tuning local sur Apple Silicon (M3 Max 128 GB).
---

# Datasets Fine-Tuning MLX — Inventaire

Catalogue des datasets d'entrainement pour fine-tuning local sur Apple Silicon (M3 Max 128 GB).
Verifier l'etat reel (wc -l) avant de citer ces chiffres.
Derniere verification: 2026-04-22.

> **Deux formats XML coexistent dans la famille Qwen3/3.5** — ne pas confondre.
> Detail complet: skill `intellisoins-mlx:qwen3-finetuning-tool-calling`.

## Tool Calling — Format A: Qwen3 standard (JSON dans `<tool_call>`)

S'applique a: Qwen3-0.6B/4B/8B, Qwen3.5-35B-A3B, Qwen3-VL-\*. Parser serveur: `qwen3`, `qwen3_coder`, `hermes` (selon modele).

| Dataset                | Chemin                                                      | Train  | Valid | Contenu                                                  |
| ---------------------- | ----------------------------------------------------------- | ------ | ----- | -------------------------------------------------------- |
| qwen3-tool-calling     | `~/Finances_Assurances/training-data/qwen3-tool-calling/`   | 22,952 | 5,747 | 77 outils, 9 domaines, dispersion 8-14 outils/exemple    |
| qwen3-merged-v2        | `~/Finances_Assurances/training-data/qwen3-merged-v2/`      | 27,277 | 5,132 | Polyvalent + medical merged, test split (1,692)          |
| qwen3-multiturn        | `~/Finances_Assurances/training-data/qwen3-multiturn/`      | 452    | 56    | Conversations multi-turn reelles (tool_response inclus)  |
| nemotron-unified-qwen3 | `~/openclaw/pipeline/training-data/nemotron-unified-qwen3/` | 2,662  | 301   | Sessions Claude Code reelles, inclut `<think>` reasoning |

Domaines couverts (77 outils): finance (28), mail (10), eventkit (8), chrome (8),
pgvector (6), spotlight (4), reminders (4), apple_apps (5), classification (4).
Tool definitions: `~/Finances_Assurances/training-data/qwen3-tool-calling/tool_definitions_openai.json`

## Tool Calling — Format B: Qwen3-Coder / Claude-style (`<function=NAME><parameter=K>V</parameter>`)

S'applique a: **Qwen3.5-9B-MLX-4bit uniquement** (a ce jour). Parser serveur: `qwen3_coder` OBLIGATOIRE.
Le chat template officiel du modele exige ce format — ne pas convertir vers Format A.

| Dataset                   | Chemin                                                           | Train  | Valid | Contenu                                                                                                                                                                                                                        |
| ------------------------- | ---------------------------------------------------------------- | ------ | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| qwen35-9b-complete-v1-32k | `~/Finances_Assurances/training-data/qwen35-9b-complete-v1-32k/` | 11,178 | 1,964 | Heterogene: ~53% style writing (textos + courriels Michael), ~44% sessions Claude Code agentic avec tool*calls (4,880 ex), ~3% autre. p50=367 tok, p95=23K tok, max=33.5K tok. `tool_call_id: toolu*\*` d'Anthropic preserves. |

Adapters existants sur ce dataset: `qwen35-9b-micro-v1/` (100 iters), `qwen35-9b-full-v1/` (2000 iters @ max-seq 4K, loss final 2-4 oscillant).

## Multimodal / Vision (image + text)

| Dataset            | Chemin                                                    | Train     | Valid | Contenu                                                                                                                                                                                               |
| ------------------ | --------------------------------------------------------- | --------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| gui-automation     | `~/Finances_Assurances/training-data/gui-automation/`     | 812       | 91    | Sessions Claude Code → screenshot + action (navigate/click/etc.). `messages[].content = [{type:"image", image:"<path>"}, {type:"text", text:"..."}]`. `_meta`: project, url, action_type, session_id. |
| vision-screenshots | `~/Finances_Assurances/training-data/vision-screenshots/` | 5,263 JPG | —     | Pool d'images referencees par gui-automation (aussi utilisables ailleurs).                                                                                                                            |

Fusion avec un dataset texte-only (ex. qwen35-9b-complete-v1-32k): mlx-vlm 0.4.4+ gere les deux formats dans le meme run (content=string pour texte pur, content=list pour multimodal).

## Tool Calling — Format Gemma JSON (a convertir pour Qwen3)

| Dataset              | Chemin                                            | Train  | Valid | Contenu                                              |
| -------------------- | ------------------------------------------------- | ------ | ----- | ---------------------------------------------------- |
| Original polyvalent  | `~/Finances_Assurances/training-data/train.jsonl` | 22,952 | 5,738 | Source des conversions Qwen3, 94.3% sessions reelles |
| Medical IntelliSoins | `~/intellisoins-pubmed/data/gemma3-dataset/`      | 49     | 9     | 26 outils PubMed/pharma/KG, petit a enrichir         |
| Merged A+B           | `~/Finances_Assurances/training-data-merged/`     | 29,331 | 6,470 | Polyvalent + medical merged                          |

Tool definitions (Gemma): `~/Finances_Assurances/training-data/tool_definitions.json` (77 outils)
Script conversion Gemma→Qwen3: skill `intellisoins-mlx:qwen3-finetuning-tool-calling`, script `convert_gemma_to_qwen35.py`

## Style / Personnalite (pas tool calling)

| Dataset        | Chemin                                                           | Train | Valid | Usage                                               |
| -------------- | ---------------------------------------------------------------- | ----- | ----- | --------------------------------------------------- |
| email-style-v4 | `~/Finances_Assurances/training-data/email-style-v4/`            | 1,299 | 164   | Style reponse email de Michael (v1, v3 aussi dispo) |
| imessage-style | `~/Finances_Assurances/training-data/imessage-style/`            | 5,031 | 559   | Style iMessage de Michael                           |
| categorisation | `~/Finances_Assurances/training-data/train_categorisation.jsonl` | 2,432 | 608   | Transaction → categorie JSON                        |

## OCR / Classification Documents

| Dataset           | Chemin                                                                | Exemples | Usage                       |
| ----------------- | --------------------------------------------------------------------- | -------- | --------------------------- |
| ocr_examples      | `~/Finances_Assurances/training-data/ocr_examples.jsonl`              | 420      | Classification docs scannes |
| real_ocr_examples | `~/Finances_Assurances/training-data/real_ocr_examples.jsonl`         | 120      | OCR reel Apple Vision       |
| new_00_a_classer  | `~/Finances_Assurances/training-data/new_00_a_classer_examples.jsonl` | 315      | Exemples 00_A_CLASSER       |

## Embeddings

| Dataset            | Chemin                                                               | Exemples                | Usage                                                           |
| ------------------ | -------------------------------------------------------------------- | ----------------------- | --------------------------------------------------------------- |
| embedding_triplets | `~/Finances_Assurances/training-data/train_embedding_triplets.jsonl` | 2,405 train / 602 valid | Triplets (anchor, positive, negative) pour fine-tune embeddings |

## Modeles Deja Entraines

| Modele      | Base                 | Status                     | Adapters                                               | Fused        |
| ----------- | -------------------- | -------------------------- | ------------------------------------------------------ | ------------ |
| Gemma3-270M | gemma-3-270m-it-bf16 | Entraine (2000 iters)      | `~/Finances_Assurances/finetune-gemma3-270m/adapters/` | Oui (831 MB) |
| Gemma3-1B   | gemma-3-1b-it-bf16   | Config prete, pas entraine | —                                                      | —            |

## Pipeline Ollama (v0.19.0+)

Ollama v0.19.0 accepte les modeles safetensors via `ollama create --experimental`:

```bash
# 1. Fine-tune MLX
python3 -m mlx_lm lora --config config.yaml

# 2. Fuse
python3 -m mlx_lm fuse --model <base> --adapter-path ./adapters --save-path ./fused

# 3. Import Ollama (safetensors natif, runner MLX)
cat > Modelfile << EOF
FROM ./fused
SYSTEM "Mon system prompt"
EOF
ollama create mon-modele -f Modelfile --experimental
```

Le runner MLX d'Ollama utilise le KV cache avec snapshots (prefix caching automatique).
Performance testee (Qwen3.5-35B-A3B): ~87 t/s gen Ollama vs ~106 t/s mlx-lm direct.
