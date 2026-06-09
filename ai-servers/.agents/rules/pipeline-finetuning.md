---
paths:
  - "pipeline/**/*.py"
  - "pipeline/**/*.yaml"
  - "pipeline/**/*.json"
  - "adapters/**/*"
---

# Pipeline Fine-tuning & GRPO

## Pipeline (4 etapes)

```
sessions_raw.jsonl (286 MB)
  → extract_claude_sessions.py    # Filtrer sessions qualite (>3 tools, <50K tokens, pas d'error loops)
sessions_openai.jsonl (241 MB)
  → convert_anthropic_to_openai.py # Format Anthropic (tool_use/tool_result) → OpenAI (tool_calls/tool)
sessions_enriched.jsonl (241 MB)
  → enrich_openclaw_tools.py       # Ajouter schemas OpenClaw, exemples synthetiques
train.jsonl + valid.jsonl
  → build_training_dataset.py      # Tool dispersion (8-14/ex), split stratifie 90/5/5, LoRA config
```

Source: 4,969 sessions Claude Code (3 GB), 14 projets.
Dataset final: 4,658 exemples (4,641 organiques + 17 synthetiques).

## GRPO (Reinforcement Learning)

Module `pipeline/grpo/` — Group Relative Policy Optimization (DeepSeekMath/R1):

| Fichier      | Role                                                            |
| ------------ | --------------------------------------------------------------- |
| `config.py`  | GRPOConfig (modele, LoRA rank=16, lr=5e-6)                      |
| `run.py`     | CLI entry point                                                 |
| `trainer.py` | Boucle: load → freeze base → LoRA → rollout → reward → gradient |
| `rollout.py` | G=4 completions par prompt, temperature 0.7                     |
| `rewards.py` | format validation, tool call correctness, thinking quality      |
| `loss.py`    | GRPO gradient: group-normalized advantages, clipped PPO         |

Commande: `python -m grpo.run --config grpo/config.yaml --dataset prompts.jsonl`

## Adapters LoRA

| Adapter                         | Modele                    | Dataset                |
| ------------------------------- | ------------------------- | ---------------------- |
| `adapters/nemotron-unified-v1/` | Nemotron 3 Nano 30B 4-bit | nemotron-unified-clean |
| `adapters/qwen3-agentic-v1/`    | Qwen3                     | openclaw-agentic       |
| `adapters/qwen35-agentic-test/` | Qwen3.5                   | agentic-test           |

Config type: `adapter_config.json` (model, rank, alpha, scale, dropout, max_seq, lr, iters, batch).

## Datasets (9 variantes)

```
pipeline/training-data/
├── openclaw-agentic/              # Tools OpenClaw-specific
├── nemotron-hammerspoon/          # macOS automation
├── nemotron-unified-clean/        # Version nettoyee
├── nemotron-real-thinking/        # Extended thinking examples
├── nemotron-chrome-navigation/    # Browser automation
└── nemotron-unified-qwen3/        # Qwen3 optimized
```

## Tests

```bash
cd pipeline/
pytest test_extract.py -v    # Slicing, token counting, error loop detection
pytest test_convert.py -v    # Transformation Anthropic ↔ OpenAI
pytest test_enrich.py -v     # Enrichissement synthetique
pytest test_build.py -v      # Stratification, tool dispersion
```

## Tool definitions

`pipeline/tool_definitions_openclaw.json` — schema JSON OpenAI-compatible pour les tools OpenClaw
(browser_tool avec 50+ parametres).

## Skills associes

Pour le workflow complet pipeline + GRPO + Ollama import: skill `intellisoins-openclaw:openclaw-finetuning`
