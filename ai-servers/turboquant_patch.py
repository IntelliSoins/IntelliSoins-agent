"""TurboQuant V2 monkey-patch for mlx-openai-server.

Patches make_prompt_cache to return TurboQuantKVCacheV2 caches
instead of standard KVCache/RotatingKVCache, and patches SDPA
for quantized attention dispatch.

Usage: import this module before starting the server.
  import turboquant_patch
  turboquant_patch.apply(bits=3)

Environment variables:
  TURBOQUANT_BITS       — quantization bits (default: 3)
  TURBOQUANT_GROUP_SIZE — group size (default: 64)
  TURBOQUANT_DISABLED   — set to "1" to disable patching
"""

import os

_patched = False


def apply(bits=None, group_size=None):
    global _patched
    if _patched:
        return

    if os.environ.get("TURBOQUANT_DISABLED") == "1":
        print("[turboquant] Disabled via TURBOQUANT_DISABLED=1")
        return

    bits = bits or int(os.environ.get("TURBOQUANT_BITS", "3"))
    group_size = group_size or int(os.environ.get("TURBOQUANT_GROUP_SIZE", "64"))

    # 1. Patch SDPA dispatch
    import turboquant.patch as tq_patch
    tq_patch.apply()

    # 2. Patch make_prompt_cache to return TurboQuant caches
    from turboquant.cache_v2 import TurboQuantKVCacheV2
    import mlx_lm.models.cache as _cache

    _original_make = _cache.make_prompt_cache

    def _tq_make_prompt_cache(model, max_kv_size=None):
        # Extract head_dim from model
        head_dim = 128  # safe default
        if hasattr(model, "args"):
            if hasattr(model.args, "head_dim") and getattr(model.args, "head_dim") is not None:
                head_dim = model.args.head_dim
            elif hasattr(model.args, "text_config") and isinstance(model.args.text_config, dict) and "head_dim" in model.args.text_config:
                head_dim = model.args.text_config["head_dim"]
            elif hasattr(model.args, "text_config") and hasattr(model.args.text_config, "head_dim") and getattr(model.args.text_config, "head_dim") is not None:
                head_dim = model.args.text_config.head_dim

        if max_kv_size is not None:
            caches = _original_make(model, max_kv_size)
        else:
            caches = _original_make(model)

        target_classes = []
        if hasattr(_cache, "KVCache"):
            target_classes.append(_cache.KVCache)
        if hasattr(_cache, "RotatingKVCache"):
            target_classes.append(_cache.RotatingKVCache)
        target_classes = tuple(target_classes)

        new_caches = []
        replaced_count = 0
        kept_count = {}
        for i, c in enumerate(caches):
            if isinstance(c, target_classes):
                new_c = TurboQuantKVCacheV2(
                    head_dim=head_dim,
                    bits=bits,
                    group_size=group_size,
                    seed=42 + i,
                )
                new_caches.append(new_c)
                replaced_count += 1
            else:
                new_caches.append(c)
                type_name = type(c).__name__
                kept_count[type_name] = kept_count.get(type_name, 0) + 1

        kept_str = ", ".join(f"{k}: {v}" for k, v in kept_count.items()) or "None"
        print(f"[turboquant] Prompt cache initialization: Replaced {replaced_count} caches with TurboQuantKVCacheV2. Kept original caches: {kept_str}")

        return new_caches

    _cache.make_prompt_cache = _tq_make_prompt_cache
    _patched = True
    print(f"[turboquant] KV-cache compression active: V2 {bits}-bit, group_size={group_size}")
