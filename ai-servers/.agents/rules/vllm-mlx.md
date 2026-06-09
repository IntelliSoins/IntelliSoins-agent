# Rule - vLLM-MLX Local Inference & Audio (VibeVoice)

## Path: `file:///Users/michaelahern/ai-servers/.agents/rules/vllm-mlx.md`

## Context & Scope

Cette règle s'applique à la gestion du serveur d'inférence vLLM-MLX local (de waybarrios) et de ses modèles de voix associés (notamment VibeVoice de Microsoft). Elle définit comment lancer, configurer et tester ces services sur cette machine.

## Installation & Runtime

- Le serveur s'exécute dans un environnement virtuel Python 3.12 isolé à l'emplacement : `/Users/michaelahern/.venvs/vllm-mlx/`
- Binaire d'exécution à appeler : `/Users/michaelahern/.venvs/vllm-mlx/bin/vllm-mlx`
- Démarrage typique du serveur :
  ```bash
  /Users/michaelahern/.venvs/vllm-mlx/bin/vllm-mlx serve <model-id> --port <port>
  ```

## Modèles configurés & validés

- **VibeVoice** :
  - ID du modèle Hugging Face : `microsoft/VibeVoice-Realtime-0.5B`
  - ID de la version MLX 4-bit optimisée (utilisée par vllm-mlx) : `mlx-community/VibeVoice-Realtime-0.5B-4bit` (alias `"vibevoice"`)
  - Voix de test validée : `en-Emma_woman` (les voix doivent être fournies via les paramètres de requête FastAPI de type Query String)

## Validation de l'inférence

- Endpoint de test FastAPI pour la synthèse vocale en local :
  ```bash
  curl -G "http://localhost:8099/v1/audio/speech" \
    --data-urlencode "model=vibevoice" \
    --data-urlencode "input=Hello from VibeVoice" \
    --data-urlencode "voice=en-Emma_woman" \
    --output output.wav
  ```
- Logs de diagnostic : rediriger la sortie du serveur vers `/Users/michaelahern/ai-servers/logs/vllm-mlx-server.log` pour le suivi des erreurs et du chargement des tenseurs.
