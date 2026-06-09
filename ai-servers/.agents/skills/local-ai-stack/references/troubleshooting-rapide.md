## Troubleshooting rapide

| Symptôme                        | Cause probable                     | Fix                                                                                                   |
| ------------------------------- | ---------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Serveur DOWN, pas de PID        | Crash ou pas démarré               | `aictl restart <name>`                                                                                |
| Health retourne 000             | Pas en cours d'exécution           | Vérifier logs, `aictl restart <name>`                                                                 |
| Tous les serveurs PRO-G40 DOWN  | Disque non monté                   | Monter le disque, KeepAlive redémarre auto                                                            |
| Conflit de port                 | Autre process sur le même port     | `lsof -i TCP:<port>` pour identifier                                                                  |
| `aictl` non trouvé              | Symlink manquant                   | `ln -sf ~/ai-servers/aictl ~/.local/bin/aictl`                                                        |
| LaunchAgent introuvable         | Pas installé                       | `aictl install`                                                                                       |
| Master key manquante (keychain) | Clé non créée ou service différent | `security find-generic-password -a "$USER" -s litellm-master-key -w` (message d'erreur = clé absente) |
