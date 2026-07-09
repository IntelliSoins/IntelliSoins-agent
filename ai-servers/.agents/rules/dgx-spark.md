---
paths:
  - "~/ai-servers/**"
  - "**/ai-spark/**"
  - "**/*spark*"
  - "**/servers.yaml"
---

# DGX Spark (spark-a4cf) — Serveur d'inférence GB10 sur le mesh WireGuard

NVIDIA DGX Spark **GB10** (aarch64, 121 Go de mémoire unifiée, ~3.7 To libres), hostname `spark-a4cf`, utilisateur `intellisoins`. Sert LLM + embeddings + reranker + docling au mesh WG. Déployé et validé bout-en-bout le 2026-07-08. Charger quand on mentionne « spark », « DGX », « GB10 », « sparkctl », « 10.0.0.5 », « ai-spark ».

## Accès

| Chemin                   | Valeur                                                                                                                                                                                                                                                                                                                          |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Mesh WG (primaire)       | `ssh spark` → `intellisoins@10.0.0.5` (clé `id_ed25519`, entrée dans `~/.ssh/config`)                                                                                                                                                                                                                                           |
| LAN (secours si WG down) | `intellisoins@spark-a4cf.local` / `192.168.2.149` (clé NVIDIA Sync via `Host dgx_spark`)                                                                                                                                                                                                                                        |
| Hub WG                   | peer enregistré sur le VPS `10.0.0.1` (`/etc/wireguard/wg0.conf`, AllowedIPs `10.0.0.5/32`)                                                                                                                                                                                                                                     |
| Pubkey WG                | archivée dans Proton Pass, note « WireGuard DGX Spark (spark-a4cf) », vault Personal                                                                                                                                                                                                                                            |
| sudo                     | **NOPASSWD actif** (`/etc/sudoers.d/99-intellisoins`, choix Michael 2026-07-08) : maintenance UFW/WireGuard/apt autonome possible via SSH.                                                                                                                                                                                      |
| UFW                      | SSH ouvert partout (LAN + mesh) ; ports AI accessibles **seulement via le mesh** 10.0.0.0/24                                                                                                                                                                                                                                    |
| ⚠️ Docker vs UFW         | Docker CONTOURNE UFW (chaîne DOCKER avant ufw) → les DENY seuls ne suffisent PAS. Les conteneurs publient donc sur `10.0.0.5:PORT` + `127.0.0.1:PORT` (jamais 0.0.0.0) ; drop-in systemd `docker.service.d/10-after-wireguard.conf` garantit wg0 up avant Docker au boot. Vérifié 2026-07-08 : LAN bloqué, mesh + localhost OK. |

## Services (docker compose, `~/ai-spark/` sur le Spark)

Gérés par **`~/ai-spark/sparkctl`** (équivalent aictl) : `up/down/status/logs {core|llm}` + `sleep/wake` (mode sommeil LLM) + `finetune start/stop`.

| Service          | Port | Profil | Modèle / image                                                                                                                                                 | Note                                                                    |
| ---------------- | ---- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| spark-vllm-llm   | 8000 | `llm`  | **`/models/qwen36-fable5-nvfp4`** (vLLM) — fine-tune dgx-fable5-mix 2026-07-09, servi sous le nom `nvidia/Qwen3.6-35B-A3B-NVFP4` + alias `qwen36-fable5-nvfp4` | 131k contexte, ~55 Go, thinking mode actif (`reasoning_content` séparé) |
| spark-embeddings | 8084 | `core` | `voyageai/voyage-4-nano` (vLLM)                                                                                                                                | 2048 dims — voir recette obligatoire ci-dessous                         |
| spark-reranker   | 8085 | `core` | `BAAI/bge-reranker-v2-m3` (vLLM)                                                                                                                               | `--runner pooling`                                                      |
| spark-docling    | 5010 | `core` | docling-serve                                                                                                                                                  | API REST directe (pas dans LiteLLM)                                     |

`sparkctl finetune start` = protection anti-catastrophe mémoire : arrête le LLM (~100 Go libérés) et ouvre le container NGC PyTorch (workspace persistant) ; `finetune stop` relance le LLM.

## Modèle fine-tuné qwen36-fable5-nvfp4 (déployé 2026-07-09)

LoRA r=16 (mix dgx-fable5, 7888 ex/30M tok, eval_loss 1.364, token acc 0.701) mergé puis quantizé **NVFP4 miroir de la recette NVIDIA** (FP8 attention ×130, NVFP4 g16 experts ×160, mtp/gates/conv1d bf16). Checkpoint : `~/finetune-workspace/qwen36-fable5-nvfp4` (21 Go + mtp 1.7 Go + vision 0.9 Go), bind-monté ro dans le compose. Scripts (aussi dans `~/openclaw/pipeline/training-data/dgx-fable5-mix/`) : `merge_and_nvfp4.py` (merge CPU + PTQ ; **modelopt ≥0.45 requis** — 0.37 saute les experts fusionnés Qwen3.5-MoE → 66 Go bf16), `inject_mtp.py` (transformers jette `mtp.*` au merge → réinjection des 19 tenseurs bf16 du base), `fixup_to_vl.py` (layout `Qwen3_5MoeForConditionalGeneration` + tour vision NVIDIA — vLLM 0.24 ne supporte PAS le MTP de la classe texte-seule `Qwen3_5MoeForCausalLM`). Rollback : remettre `nvidia/Qwen3.6-35B-A3B-NVFP4` dans le compose (toujours en cache HF).

**Speculative decoding MTP (validé A/B 2026-07-09)** : `--speculative-config '{"method":"mtp","num_speculative_tokens":3,"moe_backend":"triton"}'` — `moe_backend triton` OBLIGATOIRE (draft MTP bf16 ; marlin global ne supporte pas le MoE non quantizé → crash au boot). Gain réel single-stream : 58→68 tok/s (**+18 %**, PAS 2x — MoE A3B : les tokens vérifiés en batch activent des experts différents, la BP mémoire GB10 ne s'amortit pas comme sur un dense). Acceptance ~70 % (benchmark) / ~39 % (charge agentique réelle). k=2 testé : pas mieux (~65 tok/s).

## Mode sommeil vLLM (sleep/wake, validé 2026-07-08)

`sparkctl sleep` / `sparkctl wake` = pause rapide du LLM sans reboot (`--enable-sleep-mode` + `VLLM_SERVER_DEV_MODE=1` dans le compose ; endpoints `/sleep /wake_up /is_sleeping`, mesh+localhost seulement).

| Opération                  | Durée    | Mémoire                                                 |
| -------------------------- | -------- | ------------------------------------------------------- |
| `sleep` (niveau 1)         | ~9 s     | libère ~60 Go (KV cache jeté, poids parqués en RAM CPU) |
| `wake`                     | ~60 s    | restaure tout ; qualité vérifiée (3 cycles)             |
| reboot complet (référence) | ~3-5 min | —                                                       |

- **Niveau 1 SEULEMENT.** Le niveau 2 jette les poids et `/wake_up` ne les recharge PAS (conçu pour le swap de poids RLHF) → charabia vérifié. Ne jamais exposer level=2 dans sparkctl.
- **Coût résiduel** : après le 1er sleep, ~16 Go de RAM restent réservés (buffer CPU des poids, réutilisé — ne grossit pas aux cycles suivants) ; `docker compose --profile llm restart` les récupère.
- **Fine-tuning lourd** : rester sur `finetune start` (down complet, ~85-100 Go libérés) ; sleep = LoRA léger / pauses courtes.
- **Patch upstream obligatoire** : bug vLLM 0.24.0 (encore présent sur main 2026-07-08) — avec KV fp8 + flashinfer/MTP, `init_fp8_kv_scales` crash au wake (`'list' object has no attribute 'zero_'`). Corrigé par `~/ai-spark/patches/gpu_model_runner.py` bind-monté ro dans le conteneur ; **l'image est pinnée par digest** (`vllm/vllm-openai@sha256:251eba5c…`) pour garder patch et image cohérents. Toute mise à jour d'image = re-extraire le fichier, réappliquer le patch (en-tête `PATCH ai-spark`), re-pinner le digest. Backups : `docker-compose.yml.bak-20260708-sleepmode`, `sparkctl.bak-20260708-sleepmode`.

## ⚠️ Recette embeddings voyage-4-nano sur vLLM (NE PAS simplifier)

Sans ces flags, crash-loop `ValueError: no module or parameter named 'linear' in Qwen3ForEmbedding` (10 restarts observés au déploiement). Recette officielle de la carte HF `voyageai/voyage-4-nano` § "Via vllm" :

```
--runner pooling --convert embed
--hf-overrides '{"architectures": ["VoyageQwen3BidirectionalEmbedModel"]}'
--pooler-config '{"pooling_type": "MEAN"}'
--dtype bfloat16 --max-model-len 32768 --enforce-eager --trust-remote-code
```

**Équivalence prouvée** avec BHS5/Infinity (10.0.0.3:8004) : cosinus **0.999965** sur le même texte → vecteurs pgvector interchangeables, aucun ré-embedding. Les prompts requête/document (`Represent the query for retrieving supporting documents: ` / `Represent the document for retrieval: `) sont à la charge du client.

## Tunnel sparklan — peering WG direct Mac↔Spark via LAN (2026-07-08)

Bypass du hub VPS pour les ports AI quand le Mac est à la maison : **42 ms → ~4 ms** de RTT, bande passante gigabit locale. Clés et sous-réseau **distincts du mesh** (aucun conflit avec l'app WireGuard `wg-full`).

| Côté  | Interface  | IP         | Détail                                                                                                                                |
| ----- | ---------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Spark | `wg1`      | `10.0.1.1` | `ListenPort 51821`, UFW allow UDP 51821 depuis `192.168.2.0/24` seulement, `wg-quick@wg1` enabled                                     |
| Mac   | `sparklan` | `10.0.1.2` | `/opt/homebrew/etc/wireguard/sparklan.conf` (wg-quick brew), endpoint `192.168.2.149:51821`, LaunchDaemon `com.michaelahern.sparklan` |

- **Activation/réparation Mac** : `sudo /opt/homebrew/etc/wireguard/activate-sparklan.sh` (idempotent : up + LaunchDaemon + vérification).
- Le compose publie aussi le LLM sur `10.0.1.1:8000` (drop-in systemd étendu : Docker attend `wg-quick@wg1` en plus de `wg0`).
- **LiteLLM :8092 route seul** : 2 déploiements `spark-qwen3.6-35b` (weight 9 → `10.0.1.1` LAN ; weight 1 → `10.0.0.5` mesh). Hors maison, le LAN échoue → cooldown 60 s → tout passe par le mesh automatiquement. Rien à toucher côté clients.
- ⚠️ Endpoint = IP DHCP du Spark (`192.168.2.149`) : faire une réservation DHCP sur le routeur, sinon re-pointer `sparklan.conf` si l'IP change (le fallback mesh couvre l'intervalle).
- `AllowedIPs` Mac = `10.0.1.1/32` SEULEMENT — ne jamais y mettre `10.0.0.5` (ça volerait la route mesh et blackholerait le Spark hors maison).

## LiteLLM Mac (:8092) — modèles exposés

`litellm-proxy/config.yaml` (commit `a38f501`) :

| model_name                 | provider                                   | api_base                                  |
| -------------------------- | ------------------------------------------ | ----------------------------------------- |
| `spark-qwen3.6-35b`        | `hosted_vllm/nvidia/Qwen3.6-35B-A3B-NVFP4` | `http://10.0.0.5:8000/v1`                 |
| `spark-embeddings`         | `hosted_vllm/voyageai/voyage-4-nano`       | `http://10.0.0.5:8084/v1`                 |
| `spark-bge-reranker-v2-m3` | `hosted_vllm/BAAI/bge-reranker-v2-m3`      | `http://10.0.0.5:8085/v1`                 |
| `spark-translate`          | alias → `spark-qwen3.6-35b`                | (remplace live-translator :6060, disparu) |

**⚠️ Rerank vLLM = provider `hosted_vllm/`, JAMAIS `infinity/`** : vLLM renvoie `document` comme objet `{text, multi_modal}` alors que le provider infinity attend un string → erreur de validation Pydantic `RerankResponse`. (Le `infinity/` local :8085 du Mac reste correct : c'est un vrai serveur Infinity.)

## Frontières

- **Stack Mac intouchée** : whisper fine-tuné, voxcpm2, gemma4 restent locaux (latence Hammerspoon + fine-tunes MLX inexistants ailleurs).
- **BHS5 (10.0.0.3)** continue de servir voyage-4-nano + bge-reranker via Infinity `127.0.0.1:8004` (localhost only, accès via ssh) pour le pipeline VPS.
- opencode/clients passent par LiteLLM :8092 (fallbacks + budgets), pas d'accès direct au Spark sauf docling.
