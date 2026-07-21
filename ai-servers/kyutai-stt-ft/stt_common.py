# Copyright (c) 2026 Michael Ahern — MIT.
"""Utilitaires partagés pour le fine-tuning LoRA MLX de Kyutai STT (stt-1b-en_fr).

Sémantique portée de kyutai-labs/moshi (LMModel.forward, PyTorch) et de
jploski/moshi-finetune (Interleaver) — voir README.md. Points clés :
- dep_q=0 (pas de depformer) et delays tous à 0 pour les modèles STT →
  l'entraînement se réduit à : input[t] = codes[t-1] (initial au t=0),
  loss CE sur le stream texte seulement.
- zero_token (-1) = « pas d'embedding, pas de loss » (ScaledEmbedding.zero_idx).
- Le délai texte↔audio de 0.5 s (stt_config.audio_delay_seconds) est appliqué
  aux alignements (mots décalés de +0.5 s) + préfixe texte zéroé, comme
  Interleaver(audio_delay=-0.5) dans train_stt.py de jploski.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx
import sentencepiece
from huggingface_hub import snapshot_download

DEFAULT_HF_REPO = "kyutai/stt-1b-en_fr-mlx"
FRAME_RATE = 12.5  # mimi, 80 ms par frame
SAMPLE_RATE = 24000
ZERO_TOKEN = -1  # zero_token_id de moshi (pas d'input, pas de loss)


@dataclass
class SttPaths:
    root: Path
    config: Path
    model: Path
    mimi: Path
    tokenizer: Path


def fetch_model(hf_repo: str = DEFAULT_HF_REPO) -> SttPaths:
    root = Path(snapshot_download(hf_repo))
    cfg = json.loads((root / "config.json").read_text())
    return SttPaths(
        root=root,
        config=root / "config.json",
        model=root / cfg.get("moshi_name", "model.safetensors"),
        mimi=root / cfg["mimi_name"],
        tokenizer=root / cfg["tokenizer_name"],
    )


def load_raw_config(paths: SttPaths) -> dict:
    return json.loads(paths.config.read_text())


def load_lm(paths: SttPaths):
    """Charge le LM STT en bf16 (mêmes étapes que moshi_mlx.run_inference)."""
    import mlx.nn as nn
    from moshi_mlx import models

    raw = load_raw_config(paths)
    lm_config = models.LmConfig.from_config_dict(raw)
    model = models.Lm(lm_config)
    model.set_dtype(mx.bfloat16)
    model.load_weights(str(paths.model), strict=True)
    _ = nn  # silence unused-import linters without dropping parity with run_inference
    return model, lm_config, raw


def load_mimi(paths: SttPaths, n_q: int = 32):
    from moshi_mlx import models

    mimi = models.mimi.Mimi(models.mimi_202407(n_q))
    mimi.load_pytorch_weights(str(paths.mimi), strict=True)
    return mimi


def load_text_tokenizer(paths: SttPaths) -> sentencepiece.SentencePieceProcessor:
    return sentencepiece.SentencePieceProcessor(str(paths.tokenizer))


def build_text_stream(
    words: list[tuple[str, float, float]],
    num_frames: int,
    tokenizer: sentencepiece.SentencePieceProcessor,
    text_padding: int,
    end_of_text_padding: int,
    audio_delay: float,
    keep_and_shift: bool = False,
) -> list[int]:
    """Port exact de Interleaver.build_token_stream (moshi-finetune) pour un
    seul locuteur, avec le décalage audio_delay (>0 = le texte suit l'audio).

    - chaque mot est tokenisé individuellement (sans BOS) ;
    - le premier token d'un mot tombe à la frame où le mot commence (décalé) ;
    - un token max par frame ; la frame de padding juste avant un mot devient
      end_of_text_padding (0) ;
    - les frames entre la fin des tokens et la fin du mot = in_word_padding
      (= text_padding, 3) ;
    - le préfixe (audio_delay) est zéroé (ZERO_TOKEN → pas de loss).
    """
    from collections import deque

    aligned: list[tuple[list[int], float, float]] = []
    for word, start, end in words:
        if end <= start:
            continue
        toks = tokenizer.encode(word.strip())
        if not toks:
            continue
        aligned.append((toks, start + audio_delay, end + audio_delay))
    aligned.sort(key=lambda a: a[1])

    text_tokens = [text_padding] * num_frames
    i = 0
    queue: deque = deque()
    last_word_end = -1
    for t in range(num_frames):
        while i < len(aligned) and aligned[i][1] * FRAME_RATE < t + 1:
            toks, _start, end = aligned[i]
            last_word_end = int(end * FRAME_RATE)
            if keep_and_shift:
                queue.extend(toks)
            else:
                queue = deque(toks)
            i += 1
        if queue:
            if t > 0 and text_tokens[t - 1] == text_padding:
                text_tokens[t - 1] = end_of_text_padding
            text_tokens[t] = queue.popleft()
        elif t <= last_word_end:
            text_tokens[t] = text_padding  # in_word_padding
    prefix = int(FRAME_RATE * audio_delay)
    if prefix > 0:
        text_tokens[:prefix] = [ZERO_TOKEN] * prefix
    return text_tokens


def initial_token(raw_config: dict) -> tuple[int, int]:
    """(texte, audio) : tokens initiaux du tout premier pas de temps.

    Convention moshi : text_initial = text_card (8000), audio_initial = card (2048).
    """
    return raw_config["text_card"], raw_config["card"]


def frames_for_duration(duration_sec: float) -> int:
    return math.ceil(duration_sec * FRAME_RATE)
