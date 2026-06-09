## Toujours router via le LiteLLM Proxy (host perso uniquement)

URL : `http://127.0.0.1:8092/v1` (OpenAI-compatible) — port 8092 sur 127.0.0.1. **C'est le proxy LiteLLM personnel installé sur le disque macOS**, pas celui de l'application IntelliSoins en Docker (cf. section Périmètre ci-dessus).

Master key : `security find-generic-password -a "$USER" -s litellm-master-key -w`
(macOS Keychain. JAMAIS hardcoder, JAMAIS écrire dans .env d'un projet — ni perso, ni IntelliSoins.)

**Ne pas** appeler directement `127.0.0.1:8080-8089` (ports MLX) — perte de spend tracking, cache, fallbacks.

**Ne pas confondre** avec le LiteLLM IntelliSoins Docker (port et auth différents, voir `litellm.md`).
