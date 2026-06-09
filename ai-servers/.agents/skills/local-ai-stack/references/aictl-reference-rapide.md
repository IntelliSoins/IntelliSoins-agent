## aictl — Référence rapide

| Commande               | Action                                               |
| ---------------------- | ---------------------------------------------------- |
| `aictl status`         | Table live : PID, port, RAM, uptime                  |
| `aictl health`         | HTTP health checks sur tous les ports                |
| `aictl list`           | Registre des serveurs (nom, port, catégorie, disque) |
| `aictl start <name>`   | Démarrer un serveur                                  |
| `aictl stop <name>`    | Arrêter un serveur                                   |
| `aictl restart <name>` | Stop + start                                         |
| `aictl start all`      | Démarrer tous les serveurs                           |
| `aictl logs <name>`    | `tail -f` des logs serveur                           |
| `aictl install`        | Régénérer les LaunchAgents depuis servers.yaml       |
| `aictl uninstall`      | Supprimer tous les LaunchAgents                      |

`aictl` non trouvé → `ln -sf ~/ai-servers/aictl ~/.local/bin/aictl`
