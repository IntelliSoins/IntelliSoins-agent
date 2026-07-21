# Copyright (c) 2026 Michael Ahern — MIT.
"""Fine-tuning LoRA natif MLX de kyutai/stt-1b-en_fr sur Apple Silicon.

Usage :
  python train.py --data-dir data/train --run-dir runs/v1 \
      [--rank 32 --scaling 2.0 --lr 1e-5 --batch-size 4 --epochs 4]

Sauvegarde runs/<name>/adapters.safetensors (+ adapters_config.json) — à
fusionner ensuite avec merge_lora.py pour produire un model.safetensors
utilisable par moshi-mlx.
"""

import argparse
import json
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np

import lora_lm
import stt_common as C


def load_dataset(data_dir: Path) -> list[np.ndarray]:
    index = json.loads((data_dir / "index.json").read_text())
    return [np.load(data_dir / item["npz"])["codes"] for item in index]


def batches(samples: list[np.ndarray], batch_size: int, rng: np.random.Generator):
    """Bucketing par longueur pour limiter le padding, ordre des buckets mélangé."""
    order = sorted(range(len(samples)), key=lambda i: samples[i].shape[-1])
    groups = [order[i : i + batch_size] for i in range(0, len(order), batch_size)]
    rng.shuffle(groups)
    for g in groups:
        T = max(samples[i].shape[-1] for i in g)
        batch = np.full((len(g), samples[g[0]].shape[0], T), C.ZERO_TOKEN, dtype=np.int32)
        for j, i in enumerate(g):
            batch[j, :, : samples[i].shape[-1]] = samples[i]
        yield mx.array(batch)


def collect_lora_params(model) -> dict[str, mx.array]:
    out = {}
    for li, layer in enumerate(model.transformer.layers):
        for name, mod in (
            ("self_attn.in_proj", layer.self_attn.in_proj),
            ("self_attn.out_proj", layer.self_attn.out_proj),
            ("gating.linear_in", layer.gating.linear_in),
            ("gating.linear_out", layer.gating.linear_out),
        ):
            out[f"transformer.layers.{li}.{name}.lora_a"] = mod.lora_a
            out[f"transformer.layers.{li}.{name}.lora_b"] = mod.lora_b
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--hf-repo", default=C.DEFAULT_HF_REPO)
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--scaling", type=float, default=2.0)
    ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--warmup-pct", type=float, default=0.1)
    ap.add_argument("--text-padding-weight", type=float, default=0.5)
    ap.add_argument("--grad-clip", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--log-freq", type=int, default=10)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "train_args.json").write_text(json.dumps(vars(args), indent=1))

    mx.random.seed(args.seed)
    rng = np.random.default_rng(args.seed)

    paths = C.fetch_model(args.hf_repo)
    model, _lm_config, raw = C.load_lm(paths)
    text_initial, audio_initial = C.initial_token(raw)

    lora_lm.inject_lora(model, rank=args.rank, scaling=args.scaling)
    lora_lm.freeze_non_lora(model)
    n_train = sum(v.size for v in collect_lora_params(model).values())
    print(f"paramètres LoRA entraînables : {n_train / 1e6:.2f} M")

    samples = load_dataset(Path(args.data_dir))
    steps_per_epoch = (len(samples) + args.batch_size - 1) // args.batch_size
    total_steps = steps_per_epoch * args.epochs
    warmup = max(1, int(total_steps * args.warmup_pct))
    schedule = optim.join_schedules(
        [optim.linear_schedule(0.0, args.lr, warmup),
         optim.cosine_decay(args.lr, total_steps - warmup)],
        [warmup],
    )
    optimizer = optim.AdamW(learning_rate=schedule, betas=[0.9, 0.95], weight_decay=0.1)

    def loss_fn(mdl, codes):
        loss, _ = lora_lm.stt_text_loss(
            mdl, codes, text_initial, audio_initial,
            text_padding_weight=args.text_padding_weight,
        )
        return loss

    value_and_grad = nn.value_and_grad(model, loss_fn)
    step = 0
    t0 = time.time()
    for epoch in range(args.epochs):
        epoch_losses = []
        for codes in batches(samples, args.batch_size, rng):
            loss, grads = value_and_grad(model, codes)
            grads, _ = optim.clip_grad_norm(grads, args.grad_clip)
            optimizer.update(model, grads)
            mx.eval(model.parameters(), optimizer.state, loss)
            step += 1
            epoch_losses.append(loss.item())
            if step % args.log_freq == 0:
                frames = codes.shape[0] * codes.shape[-1]
                print(
                    f"epoch {epoch + 1} step {step}/{total_steps} "
                    f"loss {np.mean(epoch_losses[-args.log_freq:]):.4f} "
                    f"({frames / (time.time() - t0) * args.log_freq:.0f} frames/s "
                    f"| mem {mx.get_peak_memory() / 1e9:.1f} GB)"
                )
                t0 = time.time()
        print(f"== epoch {epoch + 1} : loss moyenne {np.mean(epoch_losses):.4f}")
        # un fichier par epoch : permet de choisir le meilleur point val a posteriori
        lora_np = {k: v.astype(mx.float32) for k, v in collect_lora_params(model).items()}
        mx.save_safetensors(str(run_dir / f"adapters_e{epoch + 1}.safetensors"), lora_np)
        mx.save_safetensors(str(run_dir / "adapters.safetensors"), lora_np)
    (run_dir / "adapters_config.json").write_text(
        json.dumps({"rank": args.rank, "scaling": args.scaling, "hf_repo": args.hf_repo}, indent=1)
    )
    print(f"OK — adaptateurs LoRA : {run_dir / 'adapters.safetensors'}")


if __name__ == "__main__":
    main()
