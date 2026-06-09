## PRO-G40 Disque externe

SSD `/Volumes/PRO-G40/.cache/huggingface/` requis par 3 serveurs.

| Comportement                  | Serveurs                                          |
| ----------------------------- | ------------------------------------------------- |
| **Strict** (fail sans disque) | nemotron-30b, embedding (:8084), reranker (:8085) |
| **Fallback** (cache local)    | qwen3-email, qwen3-merged, gemma3-4b              |
| **Pas de dépendance**         | Tous les autres                                   |

Les launchers attendent jusqu'à 5 minutes (60 × 5s) avant d'échouer ou de continuer.
