# Copyright (c) 2026 Michael Ahern — MIT.
"""Fusionne les adaptateurs LoRA dans les poids de base → dossier de modèle
MLX complet, directement utilisable par moshi-mlx :

  python merge_lora.py --run-dir runs/v1 --out-dir models/stt-1b-michael-mlx
  python -m moshi_mlx.run_inference --lm-config models/stt-1b-michael-mlx/config.json \
      --moshi-weights models/stt-1b-michael-mlx/model.safetensors \
      --mimi-weights models/stt-1b-michael-mlx/mimi-pytorch-e351c8d8@125.safetensors \
      --tokenizer models/stt-1b-michael-mlx/tokenizer_en_fr_audio_8000.model \
      audio.wav --temp 0
"""

import argparse
import json
import shutil
from pathlib import Path

import mlx.core as mx

import stt_common as C


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = json.loads((run_dir / "adapters_config.json").read_text())
    paths = C.fetch_model(cfg["hf_repo"])
    adapters = mx.load(str(run_dir / "adapters.safetensors"))
    scaling = cfg["scaling"]

    weights = mx.load(str(paths.model))
    merged = 0
    for name in {k.rsplit(".lora_", 1)[0] for k in adapters}:
        a = adapters[f"{name}.lora_a"]
        b = adapters[f"{name}.lora_b"]
        w = weights[f"{name}.weight"]
        weights[f"{name}.weight"] = (
            w.astype(mx.float32) + scaling * (b @ a)
        ).astype(w.dtype)
        merged += 1
    print(f"{merged} matrices fusionnées (scaling {scaling})")

    mx.save_safetensors(str(out_dir / "model.safetensors"), weights)
    for f in (paths.config, paths.mimi, paths.tokenizer):
        shutil.copy(f, out_dir / f.name)
    print(f"OK — modèle fusionné : {out_dir}")


if __name__ == "__main__":
    main()
