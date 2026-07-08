# Copyright (c) 2026 Michael Ahern — MIT.
"""LoRA minimal pour mlx.nn.Linear + forward d'entraînement causal pleine
séquence pour le LM Kyutai STT (moshi_mlx.models.Lm, dep_q=0, delays=0).

Le forward d'inférence de moshi_mlx est step-by-step avec KV cache et ne
construit jamais de masque causal ; ici on ré-exprime l'attention en pleine
séquence (mask="causal", RoPE offset 0) en réutilisant les poids des modules.
Vérifié équivalent au chemin d'inférence par equiv_test.py.
"""

import mlx.core as mx
import mlx.nn as nn


class LoRALinear(nn.Module):
    """y = base(x) + (scaling/rank) * B(A(x)) — base gelée, A/B en float32."""

    def __init__(self, base: nn.Linear, rank: int, scaling: float):
        super().__init__()
        out_d, in_d = base.weight.shape
        self.base = base
        self.rank = rank
        self.scaling = scaling
        self.lora_a = mx.random.normal((rank, in_d), scale=1.0 / rank**0.5)
        self.lora_b = mx.zeros((out_d, rank))

    def __call__(self, x: mx.array) -> mx.array:
        y = self.base(x)
        z = (x.astype(mx.float32) @ self.lora_a.T) @ self.lora_b.T
        return y + (self.scaling * z).astype(y.dtype)

    def merged_weight(self) -> mx.array:
        w = self.base.weight.astype(mx.float32)
        return (w + self.scaling * (self.lora_b @ self.lora_a)).astype(
            self.base.weight.dtype
        )


LORA_TARGETS = ("in_proj", "out_proj", "linear_in", "linear_out")


def inject_lora(model, rank: int, scaling: float) -> list[str]:
    """Enveloppe les linears attention+MLP des couches du transformer principal.

    Retourne les chemins des modules LoRA (pour sauvegarde/merge).
    """
    injected = []
    for li, layer in enumerate(model.transformer.layers):
        layer.self_attn.in_proj = LoRALinear(layer.self_attn.in_proj, rank, scaling)
        layer.self_attn.out_proj = LoRALinear(layer.self_attn.out_proj, rank, scaling)
        layer.gating.linear_in = LoRALinear(layer.gating.linear_in, rank, scaling)
        layer.gating.linear_out = LoRALinear(layer.gating.linear_out, rank, scaling)
        injected += [
            f"transformer.layers.{li}.self_attn.in_proj",
            f"transformer.layers.{li}.self_attn.out_proj",
            f"transformer.layers.{li}.gating.linear_in",
            f"transformer.layers.{li}.gating.linear_out",
        ]
    return injected


def freeze_non_lora(model) -> None:
    model.freeze()
    for layer in model.transformer.layers:
        for mod in (
            layer.self_attn.in_proj,
            layer.self_attn.out_proj,
            layer.gating.linear_in,
            layer.gating.linear_out,
        ):
            mod.unfreeze(keys=["lora_a", "lora_b"], recurse=False)


def _attn_full(attn, xs: mx.array) -> mx.array:
    """Attention causale pleine séquence avec les poids d'un modules.Attention."""
    b, t, hd = xs.shape
    cfg = attn.cfg
    qkv = attn.in_proj(xs).reshape(b, t, 3, cfg.num_heads, cfg.head_dim)
    q = qkv[:, :, 0].transpose(0, 2, 1, 3)
    k = qkv[:, :, 1].transpose(0, 2, 1, 3)
    v = qkv[:, :, 2].transpose(0, 2, 1, 3)
    if attn.rope is not None:
        q = attn.rope(q, offset=0)
        k = attn.rope(k, offset=0)
    xs = mx.fast.scaled_dot_product_attention(q, k, v, scale=attn.scale, mask="causal")
    return attn.out_proj(xs.transpose(0, 2, 1, 3).reshape(b, t, hd))


def transformer_full(model, xs: mx.array) -> mx.array:
    """model.transformer en pleine séquence causale (pas de cache)."""
    for layer in model.transformer.layers:
        xs = xs + layer.layer_scale_1(_attn_full(layer.self_attn, layer.norm1(xs)))
        xs = xs + layer.layer_scale_2(layer.gating(layer.norm2(xs)))
    return xs


def embed_codes(model, input_codes: mx.array) -> mx.array:
    """input_codes [B, 1+n_q, T] → embeddings sommés [B, T, D].

    -1 (ZERO_TOKEN) donne un embedding nul (géré par ScaledEmbedding.zero_idx).
    """
    xs = model.text_emb(input_codes[:, 0])
    for cb, emb in enumerate(model.audio_embs):
        xs = xs + emb(input_codes[:, cb + 1])
    return xs


def forward_text_logits(model, input_codes: mx.array) -> mx.array:
    xs = embed_codes(model, input_codes)
    out = transformer_full(model, xs)
    return model.text_linear(model.out_norm(out))


def stt_text_loss(
    model,
    codes: mx.array,
    text_initial: int,
    audio_initial: int,
    text_padding_ids: tuple[int, ...] = (3, 0),
    text_padding_weight: float = 0.5,
) -> tuple[mx.array, mx.array]:
    """Loss CE texte, sémantique de moshi-finetune compute_loss_with_mask.

    codes [B, 1+n_q, T] : rang 0 = stream texte cible, rangs 1.. = codes mimi.
    delays=0 → input[t] = codes[:, :, t-1], initial au premier pas.
    """
    B, K, T = codes.shape
    initial = mx.concatenate(
        [
            mx.full((B, 1, 1), text_initial, dtype=codes.dtype),
            mx.full((B, K - 1, 1), audio_initial, dtype=codes.dtype),
        ],
        axis=1,
    )
    input_codes = mx.concatenate([initial, codes[:, :, :-1]], axis=2)
    logits = forward_text_logits(model, input_codes).astype(mx.float32)

    target = codes[:, 0]  # [B, T]
    mask = target != -1
    weights = mask.astype(mx.float32)
    for pad_id in text_padding_ids:
        weights = mx.where(target == pad_id, weights * text_padding_weight, weights)
    safe_target = mx.maximum(target, 0)
    ce = nn.losses.cross_entropy(logits, safe_target, reduction="none")
    total_w = weights.sum()
    return (ce * weights).sum() / mx.maximum(total_w, 1.0), total_w
