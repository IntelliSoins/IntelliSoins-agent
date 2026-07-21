# Copyright (c) 2026 Michael Ahern — MIT.
"""Prépare le dataset de fine-tuning Kyutai STT (MLX).

Entrée : jsonl {"audio": chemin wav/m4a, "text": transcript approuvé, ...}
(format dictee-v3 de whisper-finetune).

Pour chaque clip :
1. timestamps mot-à-mot via mlx-whisper (modèle FT voix Michael par défaut —
   il a été entraîné sur ces textes, donc quasi zéro bruit de label) ;
2. audio 24 kHz mono, +0.75 s de silence à droite (le texte décalé de 0.5 s
   doit tenir dans les frames) ;
3. codes mimi (32 codebooks, 12.5 Hz) via Mimi MLX ;
4. stream texte interleavé (délai 0.5 s, préfixe zéroé) ;
5. sauvegarde npz : codes int32 [1+n_q, T] (texte en rang 0).

Usage :
  python prepare_data.py --jsonl .../train.jsonl --out-dir data/train
  python prepare_data.py --jsonl .../val.jsonl --out-dir data/val
"""

import argparse
import json
from pathlib import Path

import mlx.core as mx
import numpy as np
import sphn

import stt_common as C

# Contexte du transformer = 750 frames (60 s). Au-delà, l'attention d'inférence
# fenêtre le passé et notre forward d'entraînement divergerait → on saute.
MAX_FRAMES = 750
RIGHT_PAD_SEC = 0.75  # audio_delay 0.5 s + marge pour flusher les derniers mots

DEFAULT_WHISPER = str(
    Path.home() / "services/whisper-finetune/models/whisper-michael-mlx-v3"
)


def word_timestamps(audio_path: str, whisper_model: str, language: str) -> list[tuple[str, float, float]]:
    import mlx_whisper

    result = mlx_whisper.transcribe(
        audio_path,
        path_or_hf_repo=whisper_model,
        language=language,
        word_timestamps=True,
    )
    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            words.append((w["word"].strip(), float(w["start"]), float(w["end"])))
    return words


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--hf-repo", default=C.DEFAULT_HF_REPO)
    ap.add_argument("--whisper-model", default=DEFAULT_WHISPER)
    ap.add_argument("--language", default="fr")
    ap.add_argument("--keep-and-shift", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = C.fetch_model(args.hf_repo)
    raw = C.load_raw_config(paths)
    audio_delay = raw["stt_config"]["audio_delay_seconds"]
    text_padding = raw["existing_text_padding_id"]  # 3
    end_of_text_padding = 0
    n_q = raw["n_q"]

    mimi = C.load_mimi(paths, n_q=n_q)
    tokenizer = C.load_text_tokenizer(paths)

    index = []
    skipped = 0
    lines = [json.loads(x) for x in Path(args.jsonl).read_text().splitlines() if x.strip()]
    for i, item in enumerate(lines):
        audio_path = item["audio"]
        pcm, _sr = sphn.read(audio_path, sample_rate=C.SAMPLE_RATE)
        pcm = pcm[0]  # mono
        pad = int(RIGHT_PAD_SEC * C.SAMPLE_RATE)
        pcm = np.pad(pcm, (0, pad))
        num_frames = pcm.shape[-1] // 1920
        pcm = pcm[: num_frames * 1920]
        if num_frames > MAX_FRAMES:
            skipped += 1
            print(f"[skip >60s] {audio_path} ({num_frames} frames)")
            continue

        words = word_timestamps(audio_path, args.whisper_model, args.language)
        if not words:
            skipped += 1
            print(f"[skip vide] {audio_path}")
            continue

        codes = mimi.encode(mx.array(pcm)[None, None])  # [1, n_q, T]
        mx.eval(codes)
        codes = np.array(codes[0]).astype(np.int32)[:, :num_frames]

        text = C.build_text_stream(
            words,
            codes.shape[-1],
            tokenizer,
            text_padding=text_padding,
            end_of_text_padding=end_of_text_padding,
            audio_delay=audio_delay,
            keep_and_shift=args.keep_and_shift,
        )
        full = np.concatenate(
            [np.array(text, dtype=np.int32)[None], codes], axis=0
        )  # [1+n_q, T]
        name = f"{i:05d}.npz"
        np.savez_compressed(out_dir / name, codes=full)
        index.append({"npz": name, "audio": audio_path, "text": item.get("text", ""), "frames": int(full.shape[-1])})
        if (i + 1) % 25 == 0:
            print(f"{i + 1}/{len(lines)}")

    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1))
    print(f"OK: {len(index)} clips → {out_dir} (skipped {skipped})")


if __name__ == "__main__":
    main()
