# Copyright (c) 2026 Michael Ahern — MIT.
"""WER d'un modèle Kyutai STT MLX (base ou fusionné) sur un jsonl de clips.

  python eval_wer.py --jsonl .../val.jsonl                     # modèle de base HF
  python eval_wer.py --jsonl .../val.jsonl --model-dir models/stt-1b-michael-mlx

Décodage greedy (temp 0), même pipeline que moshi_mlx.run_inference : padding
gauche/droit stt_config, mimi 32 codebooks, LmGen step par frame de 80 ms.
"""

import argparse
import json
import re
import unicodedata
from pathlib import Path

import mlx.core as mx
import numpy as np
import sphn

import stt_common as C
from moshi_mlx import models, utils


def normalize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text.lower())
    text = re.sub(r"[^\w\s'-]", " ", text)
    return text.split()


def wer(ref: list[str], hyp: list[str]) -> tuple[int, int]:
    """(distance d'édition mots, nb mots référence)."""
    d = np.arange(len(hyp) + 1)
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
            prev, d[j] = d[j], cur
    return int(d[-1]), len(ref)


def transcribe(model, mimi, tokenizer, raw: dict, audio_path: str) -> str:
    stt = raw["stt_config"]
    pcm, _ = sphn.read(audio_path, sample_rate=C.SAMPLE_RATE)
    pad_l = int(stt.get("audio_silence_prefix_seconds", 0.0) * C.SAMPLE_RATE)
    pad_r = int((stt.get("audio_delay_seconds", 0.0) + 1.0) * C.SAMPLE_RATE)
    pcm = np.pad(pcm[0], (pad_l, pad_r))
    steps = pcm.shape[-1] // 1920
    pcm = pcm[: steps * 1920]

    codes = mimi.encode(mx.array(pcm)[None, None])  # [1, n_q, T]
    mx.eval(codes)

    for c in model.transformer_cache:
        c.reset()
    gen = models.LmGen(
        model=model,
        max_steps=steps + 8,
        text_sampler=utils.Sampler(top_k=25, temp=0.0),
        audio_sampler=utils.Sampler(top_k=250, temp=0.0),
        check=False,
    )
    pieces = []
    for t in range(codes.shape[-1]):
        text_token = gen.step(codes[:, :, t])[0].item()
        if text_token not in (0, 3):
            pieces.append(tokenizer.id_to_piece(text_token).replace("\u2581", " "))
    return "".join(pieces).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--model-dir", default=None, help="dossier fusionné ; défaut = base HF")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if args.model_dir:
        d = Path(args.model_dir)
        raw = json.loads((d / "config.json").read_text())
        paths = C.SttPaths(
            root=d,
            config=d / "config.json",
            model=d / "model.safetensors",
            mimi=d / raw["mimi_name"],
            tokenizer=d / raw["tokenizer_name"],
        )
    else:
        paths = C.fetch_model()
    model, _cfg, raw = C.load_lm(paths)
    mimi = C.load_mimi(paths, n_q=raw["n_q"])
    tokenizer = C.load_text_tokenizer(paths)

    items = [json.loads(x) for x in Path(args.jsonl).read_text().splitlines() if x.strip()]
    if args.limit:
        items = items[: args.limit]

    errs = words = 0
    for item in items:
        hyp = transcribe(model, mimi, tokenizer, raw, item["audio"])
        e, n = wer(normalize(item["text"]), normalize(hyp))
        errs += e
        words += n
        print(f"WER {e / max(n, 1):.3f}  ref: {item['text'][:60]!r}  hyp: {hyp[:60]!r}")
    print(f"\n== WER global : {errs / max(words, 1):.4f} ({errs}/{words} mots, {len(items)} clips)")


if __name__ == "__main__":
    main()
