---
name: openclaw-finetuning
description: >
  Use this project skill when Michael asks to fine-tune for OpenClaw, run the
  pipeline, build training datasets, run GRPO, create LoRA adapters, extract
  Claude sessions, convert Anthropic to OpenAI format, enrich OpenClaw tools,
  or work in the OpenClaw pipeline directory.
---

# OpenClaw Fine-Tuning

## Scope

Use this skill for the local fine-tuning pipeline under `~/openclaw/pipeline/`.
Load `references/datasets-inventory.md` only when dataset variants, dataset
stats, or generated LoRA configs matter.

## Pipeline

```bash
cd ~/openclaw/pipeline/

python extract_claude_sessions.py
python convert_anthropic_to_openai.py
python enrich_openclaw_tools.py
python build_training_dataset.py
```

Pipeline shape:

1. Extract high-quality Claude Code sessions.
2. Convert Anthropic `tool_use` / `tool_result` into OpenAI `tool_calls`.
3. Add OpenClaw tool schemas and synthetic examples.
4. Build final train/valid/test splits plus LoRA config.

## Training

```bash
mlx_lm_lora.train --config pipeline/training-data/openclaw-agentic/lora_config.yaml
```

Typical local assumptions:

- LoRA rank 16
- learning rate `5e-6`
- max sequence length 32768
- batch size 1 on M3 Max constraints

## GRPO

```bash
cd ~/openclaw/pipeline/
python -m grpo.run --config grpo/config.yaml --dataset prompts.jsonl
```

Important files:

| File              | Role                |
| ----------------- | ------------------- |
| `grpo/config.py`  | GRPOConfig          |
| `grpo/run.py`     | CLI entry point     |
| `grpo/trainer.py` | Training loop       |
| `grpo/rollout.py` | Group rollouts      |
| `grpo/rewards.py` | Reward functions    |
| `grpo/loss.py`    | GRPO/PPO-style loss |

## Validation

```bash
cd pipeline/
pytest test_extract.py -v
pytest test_convert.py -v
pytest test_enrich.py -v
pytest test_build.py -v
```
