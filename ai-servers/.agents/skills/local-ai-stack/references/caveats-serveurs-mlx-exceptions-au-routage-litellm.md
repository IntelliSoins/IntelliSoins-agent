## Caveats serveurs MLX — exceptions au routage LiteLLM

### Serveur GLiNER `:8091` — IGNORE le param `labels` (`Ihor/gliner-biomed-large-v1.0`)

Le modèle biomédical fine-tuné retourne **ses labels d'entraînement** peu importe ce que la requête HTTP demande. Validé 2026-05-11 :

```bash
curl -X POST http://localhost:8091/extract -d '{"text":"...","labels":["Drug","Disease"],"threshold":0.3}'
# Retourne quand même: Lab test, Clinical finding, Drug dosage, Drug frequency,
# Duration of treatment, Adverse effect, Author, Institution, Medical procedure,
# Demographic information, Study type
```

**Implication** : ne pas se fier au filtrage côté serveur. Filtrer **côté client** après extraction si le pipeline en aval ne sait pas mapper tous les labels (cf. désynchro mapping SQL ci-dessous).

### Embeddings MLX `:8084` — bypass autorisé si bug tiktoken

Connecter `langchain-openai` `OpenAIEmbeddings` à n'importe quel endpoint OpenAI-compat non-OpenAI (LiteLLM :8092 OU MLX :8084 direct) déclenche un bug : `check_embedding_ctx_length=True` (défaut) active tiktoken qui pré-tokenise les inputs en `int[]` côté client. Le serveur MLX rejette avec HTTP 422 `Input should be a valid string`.

Deux fixes valides :

| Fix                                                                       | Pour                                             | Contre                                                                     |
| ------------------------------------------------------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------- |
| `OpenAIEmbeddings(base_url=":8092/v1", check_embedding_ctx_length=False)` | Garde routage LiteLLM (spend tracking, fallback) | Dépendance à un flag interne langchain                                     |
| Bypass `:8084` direct via wrapper natif (cf. section RAGAs ci-dessous)    | Contrôle total, pas de magie tiktoken            | Perd le spend tracking embeddings (acceptable : haut volume / faible coût) |

**Exception explicite à l'anti-pattern #1** ("hardcoder ports MLX") : bypass `:8084` toléré **uniquement** pour les embeddings quand on parle à RAGAs / sentence-transformers / un client custom qui n'a pas besoin du tracking.
