# Copyright (c) 2026 Michael Ahern — MIT.
"""Test d'équivalence : forward d'entraînement (pleine séquence causale) vs
chemin d'inférence step-by-step avec KV cache de moshi_mlx, en teacher forcing
sur les mêmes codes. Si les logits texte concordent, le masque causal, RoPE
et les embeddings du forward d'entraînement sont corrects.

Usage : python equiv_test.py [--npz data/train/00000.npz] [--frames 200]
"""

import argparse

import mlx.core as mx
import numpy as np

import lora_lm
import stt_common as C


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--npz", default=None)
    ap.add_argument("--frames", type=int, default=200)
    args = ap.parse_args()

    paths = C.fetch_model()
    model, _lm_config, raw = C.load_lm(paths)
    # float32 : rend la comparaison déterministe (en bf16, ~2 % des argmax
    # divergent par bruit d'arrondi sur des logits quasi à égalité).
    model.set_dtype(mx.float32)
    text_initial, audio_initial = C.initial_token(raw)

    if args.npz:
        codes = np.load(args.npz)["codes"][None, :, : args.frames]
    else:
        rng = np.random.default_rng(0)
        T = args.frames
        text = rng.integers(0, raw["text_card"], size=(1, 1, T))
        audio = rng.integers(0, raw["card"], size=(1, raw["n_q"], T))
        codes = np.concatenate([text, audio], axis=1)
    codes = mx.array(codes.astype(np.int32))
    B, K, T = codes.shape
    initial = mx.concatenate(
        [
            mx.full((B, 1, 1), text_initial, dtype=codes.dtype),
            mx.full((B, K - 1, 1), audio_initial, dtype=codes.dtype),
        ],
        axis=1,
    )
    input_codes = mx.concatenate([initial, codes[:, :, :-1]], axis=2)

    # 1) forward d'entraînement pleine séquence
    full_logits = lora_lm.forward_text_logits(model, input_codes)
    mx.eval(full_logits)

    # 2) chemin d'inférence : un pas à la fois, KV cache rotatif de l'instance
    for c in model.transformer_cache:
        c.reset()
    step_logits = []
    for t in range(T):
        xs = lora_lm.embed_codes(model, input_codes[:, :, t : t + 1])
        out = model.transformer(xs, cache=model.transformer_cache)
        step_logits.append(model.text_linear(model.out_norm(out)))
    step_logits = mx.concatenate(step_logits, axis=1)
    mx.eval(step_logits)

    a = np.array(full_logits.astype(mx.float32))
    b = np.array(step_logits.astype(mx.float32))
    top1_match = (a.argmax(-1) == b.argmax(-1)).mean()
    max_diff = np.abs(a - b).max()
    print(f"top-1 identiques : {top1_match:.4%}   max |Δlogit| : {max_diff:.4f}")
    assert top1_match > 0.999, "forward d'entraînement ≠ chemin d'inférence"
    print("OK — forward d'entraînement équivalent au chemin d'inférence.")


if __name__ == "__main__":
    main()
