## omlx — FIM coder local (:8000)

Serveur LLM Apple Silicon (jundot/omlx) avec **tiered KV cache** (survit aux restarts), API OpenAI + Anthropic natives, menubar app + admin web. Géré par Homebrew, **pas via aictl**.

```bash
brew services start omlx       # auto-restart au reboot
brew services stop omlx
brew services restart omlx
curl -s http://127.0.0.1:8000/v1/models | python3 -m json.tool  # sanity check
```

Modèle déployé : `Qwen2.5-Coder-3B-bf16` (6 GB, FIM, ~30-50ms latence). Admin web : `http://127.0.0.1:8000/admin`.

Avantages vs mlx-openai-server (aictl) :

- API Anthropic native (`/v1/messages`) en plus de OpenAI
- KV cache persistant entre restarts (TTFT 49s → 1.7s, 29× speedup)
- Multi-modèles dans 1 process avec LRU eviction

Logs : `$(brew --prefix)/var/log/omlx.log` + `~/.omlx/logs/server.log`.
Rule détaillée : `~/.claude/rules/omlx.md`.

**Exposition LiteLLM + coexistence vMLX** : omlx possède `:8000` (l'autocomplete Continue FIM le vise), vMLX a déménagé sur `:8002`. Les deux sont routés par le proxy LiteLLM `:8092` via les aliases `omlx-coder` (:8000) et `vmlx-qwen36` (:8002). vMLX étant reasoning, passer `chat_template_kwargs.enable_thinking=false` pour obtenir du JSON propre (sinon il brûle `max_tokens` en raisonnement). Consommé par le hook `goal-judged.sh` (Tier 2 LLM via `/v1/chat/completions`, modèle `qwen35-9b-vision`).
