#!/usr/bin/env python3
"""
KV cache speedup benchmark for OpenAI-compatible MLX inference servers.

Mesure TTFT (Time To First Token) sur trois scenarios :
  1. COLD       — premier appel, cache miss complet
  2. WARM RAM   — meme prompt, KV cache hit en RAM
  3. WARM SSD   — apres redemarrage du serveur (option --ssd-test)
                  teste le cache persistant disque (specificite oMLX)

Le speedup attendu :
  - WARM RAM  : 50-200x sur TTFT (cache hit pur memoire)
  - WARM SSD  : 10-30x sur TTFT (oMLX revendique ~29x)

Usage :
  python3 cache-bench.py --url http://localhost:8080 --model gemma-4-31b-it-mxfp4
  python3 cache-bench.py --url ... --model ... --prompt-tokens 4096 --ssd-test
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error


def make_deterministic_prompt(target_tokens: int) -> str:
    """Genere un prompt reproductible d'environ target_tokens tokens.

    On utilise la regle empirique ~4 chars par token pour l'anglais.
    Le contenu est deterministe pour garantir un cache hit byte-pour-byte.
    """
    base = (
        "The quick brown fox jumps over the lazy dog. "
        "Pack my box with five dozen liquor jugs. "
        "How vexingly quick daft zebras jump. "
    )
    base_tokens = len(base) // 4  # ~30 tokens
    repeats = max(1, target_tokens // base_tokens)
    prompt = base * repeats
    prompt += "\n\nSummarize the previous text in one sentence."
    return prompt


def stream_chat(url: str, model: str, prompt: str, max_tokens: int,
                api_key: str = None, timeout: int = 600):
    """Appel streaming SSE vers /v1/chat/completions.

    Retourne (ttft_ms, total_seconds, completion_chunks).
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": True,
        "temperature": 0.0,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        url.rstrip("/") + "/v1/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )

    t0 = time.monotonic()
    ttft_ms = None
    chunk_count = 0

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content") or delta.get("reasoning_content") or ""
                if content:
                    if ttft_ms is None:
                        ttft_ms = (time.monotonic() - t0) * 1000.0
                    chunk_count += 1
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"HTTP {e.code}: {e.read().decode(errors='replace')[:500]}\n")
        sys.exit(2)
    except urllib.error.URLError as e:
        sys.stderr.write(f"Connexion echouee : {e.reason}\n")
        sys.exit(2)

    total_s = time.monotonic() - t0
    return ttft_ms or 0.0, total_s, chunk_count


def run_phase(label: str, url: str, model: str, prompt: str, max_tokens: int,
              api_key: str = None):
    print(f"\n>>> {label}")
    ttft, total, chunks = stream_chat(url, model, prompt, max_tokens, api_key=api_key)
    tg_tps = chunks / max(total - ttft / 1000.0, 1e-6) if chunks > 1 else 0.0
    print(f"    TTFT       : {ttft:>9.0f} ms")
    print(f"    Total      : {total:>9.2f} s")
    print(f"    Chunks gen : {chunks}")
    print(f"    Gen rate   : {tg_tps:>9.1f} chunks/s (apres TTFT)")
    return ttft, total, chunks


def main():
    ap = argparse.ArgumentParser(
        description="KV cache speedup benchmark (cold vs warm RAM vs warm SSD)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--url", default="http://localhost:8000",
                    help="Base URL du serveur (defaut: http://localhost:8000 = oMLX)")
    ap.add_argument("--model", required=True,
                    help="Nom du modele (ex: gemma-4-31b-it-mxfp4)")
    ap.add_argument("--api-key", default=None,
                    help="API key Bearer. Si omis, tente $OMLX_API_KEY puis "
                         "~/.omlx/settings.json -> auth.api_key")
    ap.add_argument("--prompt-tokens", type=int, default=1024,
                    help="Taille approximative du prompt en tokens (defaut: 1024)")
    ap.add_argument("--gen-tokens", type=int, default=64,
                    help="Tokens a generer par requete (defaut: 64, court pour mesurer TTFT)")
    ap.add_argument("--ssd-test", action="store_true",
                    help="Apres warm RAM, prompt manuel pour redemarrer le serveur "
                         "et tester le cache SSD persistant")
    ap.add_argument("--warmup-pause", type=float, default=2.0,
                    help="Pause entre cold et warm RAM (defaut: 2s)")
    args = ap.parse_args()

    prompt = make_deterministic_prompt(args.prompt_tokens)
    approx_tokens = len(prompt) // 4

    # Resolution de l'API key : --api-key > $OMLX_API_KEY > ~/.omlx/settings.json
    import os
    api_key = args.api_key or os.environ.get("OMLX_API_KEY")
    if not api_key:
        try:
            with open(os.path.expanduser("~/.omlx/settings.json")) as f:
                api_key = json.load(f).get("auth", {}).get("api_key")
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

    print("=" * 70)
    print(f"  KV Cache Speedup Benchmark")
    print("=" * 70)
    print(f"  URL       : {args.url}")
    print(f"  Model     : {args.model}")
    print(f"  Prompt    : ~{approx_tokens} tokens ({len(prompt)} chars)")
    print(f"  Gen       : {args.gen_tokens} tokens")
    print(f"  API key   : {'auto-detectee' if api_key else 'aucune'}")
    print(f"  SSD test  : {'OUI' if args.ssd_test else 'non'}")

    results = []

    # Phase 1 : COLD
    cold = run_phase(
        "Phase 1 / COLD (cache miss attendu)",
        args.url, args.model, prompt, args.gen_tokens,
        api_key=api_key,
    )
    results.append(("COLD", cold))

    if args.warmup_pause > 0:
        time.sleep(args.warmup_pause)

    # Phase 2 : WARM RAM
    warm = run_phase(
        "Phase 2 / WARM RAM (meme prompt, cache hit RAM)",
        args.url, args.model, prompt, args.gen_tokens,
        api_key=api_key,
    )
    results.append(("WARM RAM", warm))

    # Phase 3 (optionnelle) : WARM SSD apres redemarrage
    if args.ssd_test:
        print("\n" + "!" * 70)
        print("  REDEMARRE LE SERVEUR oMLX MAINTENANT")
        print("  (kill + relance, le cache RAM doit etre vide,")
        print("   mais le cache SSD persistant doit survivre)")
        print("  Appuie sur ENTREE quand le serveur est repret a accepter")
        print("  des requetes.")
        print("!" * 70)
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            print("\nAnnule.")
            sys.exit(1)

        ssd = run_phase(
            "Phase 3 / WARM SSD (apres restart, cache disque)",
            args.url, args.model, prompt, args.gen_tokens,
        )
        results.append(("WARM SSD", ssd))

    # Recap
    print("\n" + "=" * 70)
    print("  Recap (speedup vs COLD)")
    print("=" * 70)
    print(f"  {'Phase':<12} {'TTFT (ms)':>12} {'Total (s)':>12} {'TTFT x':>10}")
    print(f"  {'-'*12} {'-'*12:>12} {'-'*12:>12} {'-'*10:>10}")
    cold_ttft = results[0][1][0]
    for name, (ttft, total, _) in results:
        speedup = f"{cold_ttft/ttft:.1f}x" if ttft > 0 else "n/a"
        print(f"  {name:<12} {ttft:>12.0f} {total:>12.2f} {speedup:>10}")

    if len(results) >= 2:
        warm_ttft = results[1][1][0]
        if warm_ttft > 0 and cold_ttft / warm_ttft >= 10:
            print(f"\n  Cache RAM confirme : {cold_ttft/warm_ttft:.1f}x speedup")
        elif warm_ttft > 0:
            print(f"\n  Cache RAM faible/absent : seulement {cold_ttft/warm_ttft:.1f}x")
            print("  Verifier que le serveur active le KV cache prefix-sharing.")

    if len(results) == 3:
        ssd_ttft = results[2][1][0]
        if ssd_ttft > 0 and cold_ttft / ssd_ttft >= 10:
            print(f"  Cache SSD persistant confirme : {cold_ttft/ssd_ttft:.1f}x speedup")
            print("  (oMLX revendique ~29x sur ce scenario)")
        elif ssd_ttft > 0:
            print(f"  Cache SSD faible/absent : seulement {cold_ttft/ssd_ttft:.1f}x")


if __name__ == "__main__":
    main()
