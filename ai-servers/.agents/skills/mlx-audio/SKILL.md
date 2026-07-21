---
name: mlx-audio
description: mlx-audio — Text-to-Speech (TTS), Speech-to-Text (STT) et Speech-to-Speech (S2S) optimisé pour Apple Silicon. Supporte le clonage de voix zero-shot (VoxCPM2, F5-TTS, Voxtral) et le fine-tuning (OuteTTS via mlx-lm, F5-TTS).
paths:
  - "**/nlp/whisper-finetune/**"
---

# mlx-audio (rule on-demand)

> **Provenance** : Créé le 2026-06-08.
> **Rôle** : Guide technique pour l'inférence audio (TTS, STT), le clonage de voix zero-shot et le fine-tuning de modèles de voix (LoRA) optimisés pour Apple Silicon M3/M4 via le framework MLX.

---

## 1. Architecture & Serveur API local

Le package `mlx-audio` intègre un serveur FastAPI compatible avec l'API OpenAI (audio speech, transcriptions) et un broker d'inférence asynchrone optimisé.

- **Environnement Virtuel** : `/Users/michaelahern/.venvs/vllm-mlx/` (Python 3.12, `mlx-audio` v0.4.4)
- **Serveurs TTS locaux** : plus gérés via `servers.yaml` ; utiliser VoxCPM2/F5-TTS/OuteTTS directement ou un serveur OpenAI-compatible dédié.

---

## 2. Modèles audio & Clonage zero-shot

### VoxCPM / VoxCPM2 (MiniCPM-based)

- **Rôle** : Synthèse et clonage zero-shot robustes.
- **Status** : `mlx-community/VoxCPM2-8bit` et `VoxCPM1.5-8bit` sont pré-téléchargés dans le cache HF.
- **Clonage via CLI** :
  ```bash
  /Users/michaelahern/.venvs/vllm-mlx/bin/python -m mlx_audio.tts.generate \
      --model mlx-community/VoxCPM2-8bit \
      --text "Bonjour Michael, c'est ta voix clonée locale." \
      --ref_audio /Users/michaelahern/nlp/whisper-finetune/datasets/audio_24k/dictee-fr-20260203-111544.wav \
      --ref_text "c'est un test voir ça fonctionne bien" \
      --lang_code fr \
      --output_path /Users/michaelahern/nlp/whisper-finetune/datasets/ \
      --file_prefix test_voxcpm_fr \
      --play
  ```

#### Performance VoxCPM2 MLX (bench M3 Max 2026-07-07, checkpoint v7 8-bit + ref voix)

| inference_timesteps          | vitesse (× realtime) | usage       |
| ---------------------------- | -------------------- | ----------- |
| 10 (défaut mlx-audio)        | ~2.5×                | qualité max |
| 7 (reco model card)          | ~3.4×                | —           |
| **6 (défaut serveur local)** | ~3.8×                | équilibre   |
| 4 (borne basse officielle)   | ~4.9×                | latence min |

- Serveur dédié : `~/apple_all/voxcpm/pipeline/voxcpm2-lora/voxcpm_server_mlx.py` (port 8025, lancé par `~/ai-servers/launchers/voxcpm-tts.sh`) — modèle + ref voix chargés une fois, champs `inference_timesteps`/`cfg_value`/`stream` exposés ; `stream=true` = streaming par phrases, TTFA ~0.5 s.
- `mlx_audio.server` générique : fige timesteps à 10 et ne passe ni `inference_timesteps` ni `cfg_value` (absents de `SpeechRequest`) — éviter pour la latence.
- Le port MLX ne fait PAS de vrai streaming intra-phrase (un seul yield en fin de `generate()`) ; l'upstream PyTorch a `generate_streaming()` chunk-par-chunk. <citation>https://github.com/OpenBMB/VoxCPM (§ Streaming API), https://huggingface.co/mlx-community/VoxCPM2-8bit — consulté 2026-07-07</citation>
- CFG double le calcul DiT à chaque pas (batch 2×, `dit.py solve_euler`) ; `retry_badcase` (PyTorch) peut tripler le temps — off si latence critique.

### Voxtral-TTS (Mistral-based)

- **Rôle** : Modèle 4B de haute qualité multilingue (9 langues, 20 presets).
- **Status** : `mlx-community/Voxtral-4B-TTS-2603-mlx-4bit` est pré-téléchargé.
- **Note** : Nécessite l'installation de la dépendance `mistral-common[audio]` pour instancier le tokeniseur Tekken.

### F5-TTS (Flow-matching)

- **Rôle** : Synthèse extrêmement naturelle et expressive.
- **Clonage & Training** : Offre une version native Apple Silicon via `f5-tts-mlx`.
- **Installation** :
  ```bash
  pip install f5-tts-mlx
  ```

---

## 3. Pipelines de Fine-Tuning de la voix (LoRA)

### Approche A : OuteTTS 1.0 (via `mlx-lm lora`)

Puisque OuteTTS code le son sous forme de tokens discrets (SNAC), il est entraîné comme un modèle de langage causal standard (Llama3 ou Qwen2). Il est donc compatible avec le pipeline d'entraînement standard d'Apple (`mlx-lm lora`).

1. **Tokenisation Audio** : Convertir les WAVs d'entraînement (e.g. dans `/Users/michaelahern/nlp/whisper-finetune/datasets/audio`) en codes SNAC 24kHz.
2. **Format Dataset** : Structurer un fichier `train.jsonl` associant texte d'entrée et tokens SNAC de sortie :
   ```json
   {
     "text": "<|im_start|>user\nBonjour Michael.<|im_end|>\n<|im_start|>assistant\n<|audio_start|>[1024, 405, 304, ...]<|audio_end|><|im_end|>"
   }
   ```
3. **Entraînement LoRA** :
   ```bash
   python -m mlx_lm.lora \
       --model mlx-community/OuteTTS-1.0-0.6B-fp16 \
       --train \
       --data /path/to/dataset/ \
       --iters 1000 \
       --batch-size 4
   ```

### Approche B : F5-TTS (via `f5-tts-mlx`)

Le dépôt `f5-tts-mlx` intègre un script `train.py` pour entraîner le modèle de flow-matching sur Apple Silicon.

1. Organiser un fichier de métadonnées `metadata.csv` reliant chaque fichier WAV à son texte :
   ```csv
   audio_path|transcript
   datasets/audio/recording1.wav|Bonjour, ceci est ma voix.
   ```
2. Lancer la boucle d'entraînement MLX :
   ```bash
   python train.py --dataset_path ./metadata.csv --epochs 50
   ```
