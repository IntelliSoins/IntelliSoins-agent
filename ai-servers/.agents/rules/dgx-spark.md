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

| Service           | Port | Profil | Modèle / image                                                                                                                                                                        | Note                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ----------------- | ---- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| spark-vllm-4b     | 8000 | `llm`  | **`Qwen/Qwen3.5-4B` fine-tuné `intellisoins-tasks`** (vLLM, alias `qwen3.5-4b-intellisoins`, LoRA mergé bf16 → rewrap VL 8,8 Go) — déployé 2026-07-10 pour WEB-FORMATION-AUTH-DGX-RAG | Auth `--api-key` (`SPARK_VLLM_API_KEY` .env = SOPS env.prod VPS) ; max-model-len 32768, gpu-mem-util 0.15 (~15 Go) ; **tool calling activé 2026-07-10** (`--enable-auto-tool-choice --tool-call-parser hermes`, rollback `docker-compose.yml.bak-20260710-qwen35-4b-tools`) — `tool_choice:"required"` produit des `tool_calls` structurés, `auto` tend à raisonner en texte (trait du FT intellisoins-tasks, pas un bug) ; consommé par LiteLLM **VPS** (alias `formation-tutor`) **ET LiteLLM Mac** (`qwen3.5-4b-intellisoins`, opencode). Remplace Gemma 4 26B-A4B (retiré 2026-07-10, pas assez performant) |
| spark-embeddings  | 8084 | `core` | `voyageai/voyage-4-nano` (vLLM)                                                                                                                                                       | 2048 dims — voir recette obligatoire ci-dessous                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| spark-reranker    | 8085 | `core` | `BAAI/bge-reranker-v2-m3` (vLLM)                                                                                                                                                      | `--runner pooling`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| spark-docling     | 5010 | `core` | docling-serve                                                                                                                                                                         | API REST directe (pas dans LiteLLM)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| spark-translation | 6060 | `core` | `facebook/nllb-200-distilled-600M` (FastAPI+CUDA, build `~/ai-spark/translation/`)                                                                                                    | API REST directe (`/translate`, pas dans LiteLLM) — remplace le live-translator Mac :6060 (2026-07-10) ; publié aussi sur `10.0.1.1:6060` (sparklan) ; Hammerspoon ⌥⌘L/⌥⌘K + tool `translate`                                                                                                                                                                                                                                                                                                                                                                                                                   |
| spark-whisper     | 2022 | `core` | whisper-large-v3-turbo **fine-tuné voix Michael v3 mergé HF** (FastAPI+CUDA fp16, build `~/ai-spark/whisper/`, modèle `~/ai-spark/whisper/model/`)                                    | `/v1/audio/transcriptions` OpenAI (json/text), ~0,13 s/clip (2026-07-10, mesuré) ; **Hammerspoon migré sur le Spark :2022 primaire** le 2026-07-10 (sparklan 10.0.1.1 → fallback mesh 10.0.0.5, `init.lua:37-38/81-91`) ; Mac :2022 (MLX) reste en service (aictl) mais n'est plus dans la chaîne Hammerspoon                                                                                                                                                                                                                                                                                                   |
| spark-voxcpm-tts  | 8026 | `core` | **VoxCPM2 + LoRA Michael v8** (Nano-vLLM-VoxCPM, build `~/ai-spark/voxcpm-tts/`, LoRA `~/ai-spark/voxcpm-tts/models/michael-v8/`)                                                     | `/generate` (API native Nano-vLLM, streaming MP3) + `/v1/audio/speech` via bridge Mac :8884 ; **RTF mesuré 0.49 sur GB10** (upstream ~0.13 RTX 4090) ; GPU mem util 0.15 (~19 Go) ; **PRIMAIRE Hammerspoon (⌥v + agent vocal) depuis 2026-07-11** via bridge :8884 (sparklan primaire + mesh fallback) ; Mac MLX :8025 (v7, RTF 0.37) devient fallback local                                                                                                                                                                                                                                                    |

### VoxCPM TTS — Nano-vLLM + LoRA v8 (2026-07-10)

**Architecture** : VoxCPM2 base (openbmb/VoxCPM2, cache HF Spark) + LoRA Michael v8 (r=32, alpha=32, enable_lm+dit, 225 wav, 1000 steps, loss/diff 0.859). Serving via **Nano-vLLM-VoxCPM** (upstream RTF ~0.13 sur RTX 4090 ; **mesuré 0.49 sur GB10** — le GB10 est moins puissant, mlx-audio natif Mac reste ~25 % plus rapide en single-request).

**Benchmark 2026-07-10** (Phase 6 PASS, 3 routes validées) :

| Route                       | RTF court | RTF long | Usage                                                                               |
| --------------------------- | --------- | -------- | ----------------------------------------------------------------------------------- |
| Mac MLX :8883 (v7 8-bit)    | 0.41      | 0.37     | **Fallback local** (si Spark down) — était Hammerspoon primaire jusqu'au 2026-07-10 |
| Spark :8884 via bridge (v8) | 0.53      | 0.49     | **Hammerspoon primaire** (⌥v + agent vocal, depuis 2026-07-11) + LiteLLM/OpenClaw   |
| Spark :8026 natif (v8)      | 0.49      | —        | Debug, bas niveau                                                                   |

**Endpoints** :

- `POST /generate` — API native Nano-vLLM, streaming MP3, paramètres : `target_text`, `lora_name`, `cfg_value`, `inference_timesteps`
- `POST /encode_latents` — pré-calcul latences ref audio
- `GET /health`, `/ready`, `/info`, `/metrics`

**Accès Mac** :

- Direct Spark : `http://10.0.0.5:8026` (mesh WG) ou `http://10.0.1.1:8026` (sparklan, latence ~4ms)
- Bridge OpenAI-compat Mac : `http://127.0.0.1:8884/v1/audio/speech` (script `spark-voxcpm-bridge.py`, port :8884) — **sparklan primaire + mesh fallback** (depuis 2026-07-11, même pattern que whisper/nllb)
- LiteLLM : `spark-voxcpm-v8` → `http://127.0.0.1:8884/v1`

**Coexistence** : **Hammerspoon ⌥v + agent vocal (⌥⌘ç) utilisent le Spark v8 via :8884 depuis 2026-07-11** (v8 = dernier fine-tune, meilleure qualité voix ; tradeoff RTF 0.49 vs Mac 0.37). Le Mac conserve `voxcpm-tts` :8025 (MLX 8-bit v7) + bridge :8883 comme **fallback local** (si Spark down) et pour LiteLLM (`michael-v6-mlx-8bit` alias). Bascule fallback manuelle : si Spark down, repointer `TTS_URL` vers `:8883` dans `init.lua` et `VOICE_TTS_URL` vers `:8883` dans `voice-agent-webrtc.sh`.

**Variables d'environnement** (docker-compose.yml) :

```
NANOVLLM_MODEL_PATH=/root/.cache/huggingface/hub/models--openbmb--VoxCPM2/snapshots/bffb3df5a29440629464e5e839f4d214c8714c3d
NANOVLLM_LORA_ENABLED=true
NANOVLLM_LORA_MAX_LORA_RANK=32
NANOVLLM_LORA_MAX_LORAS=1
NANOVLLM_LORA_ENABLE_LM=true
NANOVLLM_LORA_ENABLE_DIT=true
NANOVLLM_LORA_ENABLE_PROJ=false
NANOVLLM_SERVERPOOL_GPU_MEMORY_UTILIZATION=0.15
LORA_PATH=/models/michael-v8
LORA_NAME=michael-v8
```

**Build Docker** : `cd ~/ai-spark && docker compose build voxcpm-tts` (image `spark-voxcpm-tts:latest`, base NGC PyTorch 25.11 + nano-vllm-voxcpm + flash-attn).

### Fine-tuning terminés (2026-07-10) / file GPU

- **Qwen3.5-4B LoRA `intellisoins-tasks`** : ✅ TERMINÉ 2026-07-10 20:08 (exit 0) — 986 steps, 3h48, eval_loss 1.413, eval_mean_token_accuracy 0.6972, bf16 LoRA r=16 sur base `Qwen/Qwen3.5-4B` (8,8 Go cache HF). Dataset `dgx-fable5-mix` (7888 ex/30M tok : imessage-style 6295, email-style 639, fable5-claude 948, pubmed-opus48 431, fable5-opencode 195, chrome-nav 118). Merge CPU bf16 → `~/finetune-workspace/qwen35-4b-intellisoins-merged` → rewrap VL `qwen35-4b-intellisoins-vl` (8,8 Go, layout Qwen3.5-VL pour vLLM, script `rewrap_qwen35_4b.py`). **Servi maintenant** via `spark-vllm-4b` :8000 (profil `llm`). Frameworks : TRL 0.24.0, Transformers 5.5.0, PyTorch 2.10.0 (NGC 25.11), image `spark-finetune:trained`. Adapters dans `~/finetune-workspace/adapters-qwen35-4b-tasks/` (checkpoints 850/900/950/986 + final).
- **VoxCPM v8** (voix Michael, dataset complet 225 wav du rescue) : ✅ TERMINÉ — step 999/1000, loss/diff final 0.859, 71 epochs, LoRA r=32 (enable_lm+dit). Container `voxcpm-v8-finetune`, log `~/finetune-workspace/voxcpm-v8/train-v8-spark.log`. **Servi maintenant** via `spark-voxcpm-tts` :8026 — détails rule `apple_all/voxcpm.md`.

`sparkctl finetune start` = ouvre le container NGC PyTorch (workspace persistant) ; `finetune stop` = `docker compose --profile llm down` (arrête `spark-vllm-4b` :8000 — profil `llm` **réintroduit** 2026-07-10 avec Qwen3.5-4B FT, après retrait éphémère de Gemma 4 26B le matin même). Historique rollbacks compose : `docker-compose.yml.bak-20260710-removegemma426b` (retrait Gemma 4 26B), `docker-compose.yml.bak-20260710-qwen35-4b-formation` (ajout Qwen3.5-4B FT).

## ⛔ HISTORIQUE — LLM Gemma 4 26B-A4B FP8 (déployé 2026-07-09, RETIRÉ 2026-07-10) + qwen36-fable5

> **Gemma 4 26B-A4B FP8 supprimé 2026-07-10** (pas assez performant au goût de Michael). Le LLM actuel est **Qwen3.5-4B FT intellisoins** (profil `llm`, `spark-vllm-4b` :8000) — voir table services ci-dessus. Cette section est conservée pour les rollbacks (cache HF + `.bak`) et les recettes FP8/MTP réutilisables.

**Choix FP8-Dynamic > NVFP4** : GB10 sans compute FP4 natif (NVFP4 MoE = détour Marlin W4A16) ; FP8 = chemin natif (backend MoE TRITON auto-sélectionné), qualité ~bf16, et **LoRA à chaud supporté sur base FP8** (objectif : fine-tuner sans couper le serving). Architecture 100 % standard (sliding+full attention, MoE classique, aucun conv1d) → LoRA-friendly, contrairement au Qwen3.6 hybride. Mémoire après déploiement : 65 Go disponibles avec TOUT up → marge QLoRA ~30B (~25-45 Go) **sans arrêter le LLM** (à bencher : impact tok/s pendant un epoch). ⚠️ Warning au boot « Using default MoE config » (pas de config Triton tunée pour `E=128,N=704,device_name=NVIDIA_GB10,fp8_w8a8`) : perf sous-optimale possible, tuning futur via benchmark_moe.py. Pas de `--quantization` dans le compose (compressed-tensors auto-détecté) ; patch `modelopt.py` retiré (spécifique 31B NVFP4). Rollbacks en cache HF : `nvidia/Gemma-4-31B-IT-NVFP4` (dense, ~6 tok/s solo — rejeté pour ça) via `docker-compose.yml.bak-20260709-gemma31b-dense` ; qwen36-fable5-nvfp4 via `docker-compose.yml.bak-20260709-gemma4`.

### Historique — fine-tune qwen36-fable5-nvfp4 (prod 2026-07-09, remplacé le jour même)

LoRA r=16 (mix dgx-fable5, 7888 ex/30M tok, eval_loss 1.364, token acc 0.701) mergé puis quantizé **NVFP4 miroir de la recette NVIDIA** (FP8 attention ×130, NVFP4 g16 experts ×160, mtp/gates/conv1d bf16). Checkpoint : `~/finetune-workspace/qwen36-fable5-nvfp4` (21 Go + mtp 1.7 Go + vision 0.9 Go). Scripts (aussi dans `~/openclaw/pipeline/training-data/dgx-fable5-mix/`) : `merge_and_nvfp4.py` (merge CPU + PTQ ; **modelopt ≥0.45 requis** — 0.37 saute les experts fusionnés Qwen3.5-MoE → 66 Go bf16), `inject_mtp.py` (transformers jette `mtp.*` au merge → réinjection des 19 tenseurs bf16 du base), `fixup_to_vl.py` (layout `Qwen3_5MoeForConditionalGeneration` + tour vision NVIDIA — vLLM 0.24 ne supporte PAS le MTP de la classe texte-seule `Qwen3_5MoeForCausalLM`). **Cette recette merge+requant est spécifique Qwen3.5-MoE ; pour Gemma, viser le serving LoRA à chaud (`VLLM_ALLOW_RUNTIME_LORA_UPDATING` + `/v1/load_lora_adapter`) au lieu du merge.**

**Speculative decoding MTP (Qwen seulement, validé A/B 2026-07-09)** : `--speculative-config '{"method":"mtp","num_speculative_tokens":3,"moe_backend":"triton"}'` — `moe_backend triton` OBLIGATOIRE (draft MTP bf16 ; marlin global ne supporte pas le MoE non quantizé → crash au boot). Gain réel single-stream : 58→68 tok/s (+18 %). Ne s'applique PAS à Gemma (pas de tête MTP).

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
- Le drop-in systemd étendu fait attendre Docker sur `wg-quick@wg1` (sparklan) en plus de `wg0` (mesh) au boot — nécessaire car translation/whisper/voxcpm-tts publient sur `10.0.1.1`.
- **Profil `llm`** : réintroduit 2026-07-10 avec Qwen3.5-4B FT intellisoins ( :8000, auth API key, **mesh-only** — pas publié sur sparklan). sparklan (10.0.1.1, ~4 ms) publie **seulement** translation :6060, whisper :2022 et voxcpm-tts :8026 ; embeddings :8084, reranker :8085, docling :5010 et vllm-4b :8000 restent **mesh-only** (10.0.0.5, ~82 ms via hub VPS). Vérifié 2026-07-10 (`docker compose ps` + curl depuis le Mac). Rollback Gemma 4 26B-A4B : `docker-compose.yml.bak-20260710-removegemma426b` sur le Spark.
- ⚠️ Endpoint = IP DHCP du Spark (`192.168.2.149`) : faire une réservation DHCP sur le routeur, sinon re-pointer `sparklan.conf` si l'IP change (le fallback mesh couvre l'intervalle).
- `AllowedIPs` Mac = `10.0.1.1/32` SEULEMENT — ne jamais y mettre `10.0.0.5` (ça volerait la route mesh et blackholerait le Spark hors maison).

## LiteLLM Mac (:8092) — modèles exposés

`litellm-proxy/config.yaml` (commit `a38f501`) :

| model_name                 | provider                              | api_base                   |
| -------------------------- | ------------------------------------- | -------------------------- |
| `spark-embeddings`         | `hosted_vllm/voyageai/voyage-4-nano`  | `http://10.0.0.5:8084/v1`  |
| `spark-bge-reranker-v2-m3` | `hosted_vllm/BAAI/bge-reranker-v2-m3` | `http://10.0.0.5:8085/v1`  |
| `spark-voxcpm-v8`          | `openai/spark-voxcpm-v8`              | `http://127.0.0.1:8884/v1` |

Traduction : NLLB dédié = REST direct `:6060` (spark-translation), pas de LiteLLM Mac.

LLM : `qwen3.5-4b-intellisoins` servi sur Spark `:8000` (auth API key `SPARK_VLLM_API_KEY`, mesh-only) — consommé par LiteLLM **VPS** (alias `formation-tutor`, api_base `http://10.0.0.5:8000/v1`) **ET LiteLLM Mac** (ajouté 2026-07-10 pour opencode : `model_name: qwen3.5-4b-intellisoins` dans `litellm-proxy/config.yaml`, `api_key: os.environ/SPARK_VLLM_API_KEY` depuis `litellm-proxy/.env` ; exposé dans `opencode.jsonc` comme `litellm/qwen3.5-4b-intellisoins`, ctx 32768, tool_call true). `spark-gemma4-26b` retiré 2026-07-10 (profil `llm` éphémèrement vide, réintroduit avec Qwen3.5-4B FT le soir même).

TTS : `spark-voxcpm-v8` via bridge Mac :8884 (→ Spark :8026 Nano-vLLM) ; `michael-v6-mlx-8bit` via bridge Mac :8883 (→ :8025 MLX local).

**⚠️ Rerank vLLM = provider `hosted_vllm/`, JAMAIS `infinity/`** : vLLM renvoie `document` comme objet `{text, multi_modal}` alors que le provider infinity attend un string → erreur de validation Pydantic `RerankResponse`. (Le `infinity/` local :8085 du Mac reste correct : c'est un vrai serveur Infinity.)

## Frontières

- **Stack Mac intouchée** : gemma4 omni reste local (latence Hammerspoon agent vocal + fine-tune MLX inexistant ailleurs). **whisper + voxcpm2 migrés sur Spark** pour Hammerspoon (2026-07-10/11) : whisper FT :2022 (CUDA) et voxcpm2 v8 :8026 via bridge :8884 (sparklan + mesh fallback). Le Mac conserve whisper MLX :2022 et voxcpm v7 :8025/:8883 comme fallbacks locaux.
- **BHS5 (10.0.0.3)** continue de servir voyage-4-nano + bge-reranker via Infinity `127.0.0.1:8004` (localhost only, accès via ssh) pour le pipeline VPS.
- opencode/clients passent par LiteLLM :8092 (fallbacks + budgets), pas d'accès direct au Spark sauf docling.
