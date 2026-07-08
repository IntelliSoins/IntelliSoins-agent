# Fine-tuning Kyutai STT-1B natif MLX (voix Michael)

Portage MLX du fine-tuning LoRA de `kyutai/stt-1b-en_fr` — **entraînement 100 %
local sur Apple Silicon** (M3 Max : ~5 min pour 4 epochs sur 83 min d'audio,
9,1 GB de mémoire pic). Aucun GPU CUDA requis, contrairement au chemin
communautaire jploski/moshi-finetune (PyTorch/torchrun).

## Résultats (2026-07-08, val dictee-v3 = 19 clips / 411 mots)

| Modèle                                                                    | WER       |
| ------------------------------------------------------------------------- | --------- |
| stt-1b-en_fr vanilla                                                      | 0.421     |
| **LoRA v1 (4 epochs, rank 32, lr 1e-5)** — `models/stt-1b-michael-mlx-v1` | **0.307** |
| Whisper large-v3-turbo FT v3 (référence, :2022)                           | 0.184     |

Leçons : le surapprentissage arrive vite (8 epochs lr 2e-5 rank 64 → WER 1.05,
effondrement) ; ~4 epochs avec schedule cosine complété = point robuste.
`--keep-and-shift` préserve +5,9 % de tokens (mots rapides) mais n'a pas battu
v1 sur ce val set (0.355 à epoch 4).

## Pipeline

```bash
VENV=~/.venvs/kyutai-stt/bin/python   # moshi-mlx, mlx-whisper, sphn, sentencepiece

# 1. Dataset : jsonl {audio, text} → timestamps mots (Whisper FT) + codes mimi → npz
$VENV prepare_data.py --jsonl .../train.jsonl --out-dir data/train

# 2. Entraînement LoRA (adapters par epoch dans runs/<v>/)
$VENV train.py --data-dir data/train --run-dir runs/v1 --epochs 4 --rank 32 --lr 1e-5

# 3. Fusion → dossier modèle complet compatible moshi-mlx
$VENV merge_lora.py --run-dir runs/v1 --out-dir models/stt-1b-michael-mlx-v1

# 4. WER sur le val set (base HF si --model-dir omis)
$VENV eval_wer.py --jsonl .../val.jsonl --model-dir models/stt-1b-michael-mlx-v1

# Test de non-régression du portage (forward train ≡ chemin d'inférence)
$VENV equiv_test.py
```

## Architecture du portage

- `stt_common.py` : chargement Lm/Mimi/tokenizer MLX + port de
  `Interleaver.build_token_stream` (moshi-finetune) — stream texte aligné aux
  frames mimi 12,5 Hz, délai texte↔audio 0,5 s (`stt_config`), préfixe zéroé.
- `lora_lm.py` : LoRALinear (A/B float32, base bf16 gelée) injecté dans
  in_proj/out_proj/linear_in/linear_out des 16 couches ; **forward causal
  pleine séquence** (l'inférence moshi_mlx est step-by-step avec KV cache et
  ne construit jamais de masque) — prouvé équivalent par `equiv_test.py`
  (100 % top-1 en float32, Δ logits 2e-4).
- Simplifications propres au STT : `dep_q=0` (pas de depformer), `delays`
  tous nuls, loss CE texte seulement (padding 3/0 pondéré 0,5), cibles -1
  masquées. Séquences ≤ 750 frames (60 s) = contexte du transformer.

## Utiliser le modèle fusionné

```bash
$VENV -m moshi_mlx.run_inference --lm-config models/stt-1b-michael-mlx-v1/config.json \
  --moshi-weights models/stt-1b-michael-mlx-v1/model.safetensors \
  --mimi-weights "models/stt-1b-michael-mlx-v1/mimi-pytorch-e351c8d8@125.safetensors" \
  --tokenizer models/stt-1b-michael-mlx-v1/tokenizer_en_fr_audio_8000.model \
  audio.wav --temp 0
```

Références : kyutai-labs/delayed-streams-modeling (issue #4 : pas de code de
fine-tuning officiel), jploski/moshi-finetune (recette PyTorch), moshi_mlx 0.3.0.
