## Anti-patterns à éviter

1. **Hardcoder ports MLX** : `OpenAI(base_url="http://127.0.0.1:8080/v1")` → utiliser le proxy
2. **Stocker master key dans .env de projet** : utiliser Keychain
3. **Appeler un modèle sans `aictl start` préalable** : MLX DOWN par défaut
4. **Modifier directement servers.yaml sans `aictl install`** : LaunchAgents pas régénérés
5. **Coder un fallback custom** : utiliser `router_settings` du proxy
