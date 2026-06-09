---
paths:
  - "**/litellm*ocr*"
  - "**/mistral_ocr*"
  - "**/tesseract*"
  - "**/docling*"
  - "**/ocr*"
---

# LiteLLM `/ocr` + Pass-Through OCR — Extraction de texte multi-engine

Endpoint OpenAI-style pour extraire du texte de PDFs/images via LiteLLM. Deux familles d'engines sont couvertes par ce skill :

1. **OCR natif `/v1/ocr`** — providers cloud Mistral, Azure, Vertex routés directement par LiteLLM (cost tracking + logging + fallbacks built-in).
2. **Pass-through endpoints** — OCR locaux (Tesseract, Docling, Apple Vision) exposés sous `/ocr/<engine>` via `general_settings.pass_through_endpoints` (master key + tracking partiel).

Choisir l'engine selon : confidentialité données, format source, qualité attendue, environnement de déploiement (Mac local vs VPS Linux arm64).

## Matrice de décision OCR

| Engine                                  | Type               | Confidentialité                    | Format source                                 | Qualité                                         | Déploiement                                               | Statut local Michael                                          |
| --------------------------------------- | ------------------ | ---------------------------------- | --------------------------------------------- | ----------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------- |
| `mistral-ocr-latest`                    | Cloud (Mistral EU) | Données envoyées chez Mistral      | PDF, JPG, PNG, TIFF                           | Excellente (multi-langues, structure préservée) | Cloud uniquement                                          | ✅ `MISTRAL_API_KEY` déjà configurée (proxy 8092 voxtral STT) |
| `azure/<deployment>` (Doc Intelligence) | Cloud (Azure)      | Données envoyées chez Azure        | PDF, JPG, PNG, TIFF, BMP, HEIF                | Excellente (formulaires, tables, signatures)    | Cloud uniquement                                          | ❌ Pas de subscription configurée                             |
| `vertex_ai/document-ai`                 | Cloud (Google)     | Données envoyées chez Google       | PDF, JPG, PNG, TIFF, GIF                      | Excellente (multi-langues + entité extraction)  | Cloud uniquement                                          | ❌ Pas de credentials GCP locaux                              |
| `tesseract 5.5.2`                       | Local FOSS         | 100% local, aucune sortie réseau   | PNG, JPG, TIFF (PDFs via `pdftoppm` upstream) | Bonne (langues européennes)                     | Mac local + VPS Linux arm64 (`apt install tesseract-ocr`) | ✅ Installé `brew` (binaire CLI), wrapper FastAPI à créer     |
| `docling` (IBM Research)                | Local FOSS         | 100% local                         | PDF natif (parser layout-aware)               | Très bonne (tables, formules math, structure)   | Mac local + VPS Linux arm64 (image officielle)            | ❌ Non installé (pip install docling-serve)                   |
| `ocrmac` (Apple Vision)                 | Local Mac          | 100% local, Apple Vision framework | PNG, JPG, TIFF                                | Bonne (rapide, anglais/français OK)             | Mac local UNIQUEMENT (PyObjC, pas de port Linux)          | ❌ Non installé (`pip install ocrmac`)                        |

> **Règle d'or PHI/Loi 25** : pour données patient (IntelliSoins), privilégier engines locaux (tesseract/docling) sauf si DPA signé avec Mistral EU. Cf. skill `litellm-guardrails-policies` pour Presidio sur sortie OCR.

## Matrice des features LiteLLM

| Feature           | OCR natif `/v1/ocr`                              | Pass-through `/ocr/<engine>`                          |
| ----------------- | ------------------------------------------------ | ----------------------------------------------------- |
| Cost tracking     | ✓ (auto via `model_info`)                        | ⚠️ Manuel via `cost_per_request` (param pass-through) |
| Logging callbacks | ✓ Langfuse/OTel/Datadog                          | ⚠️ Limité (request/response uniquement)               |
| End-user tracking | ✓ Header `x-litellm-end-user-id`                 | ✓ Si `forward_headers: true`                          |
| Fallbacks         | ✓ Par requête (`extra_body.fallbacks`) ou global | ❌ (pas dans le router LiteLLM)                       |
| Loadbalancing     | ✓ Plusieurs deployments même `model_name`        | ❌                                                    |
| Guardrails        | ✓ Sur output (Presidio PII, etc.)                | ❌                                                    |
| Master key auth   | ✓                                                | ✓                                                     |

## Section 1 — OCR natif `/v1/ocr` (Mistral / Azure / Vertex)

### Quick Start — SDK Python (in-process)

VERIFIE: https://docs.litellm.ai/docs/ocr (page upstream récupérée 2026-05-06).

```python
from litellm import ocr

response = ocr(
    model="mistral/mistral-ocr-latest",
    document={
        "type": "document_url",
        "document_url": "https://arxiv.org/pdf/2201.04234"
    }
)

# response.pages = [{ "index": 0, "markdown": "...", "dimensions": {...}, "images": [...] }, ...]
print(response.pages[0]["markdown"])
```

Variante async : `from litellm import aocr` (signature identique, `await aocr(...)`).

### Via Proxy local (recommandé — tracking + fallbacks)

Auth via Keychain (jamais hardcoder la master key). Cf. `~/.claude/rules/local-ai-stack.md`.

```python
import subprocess
import requests

master = subprocess.check_output([
    "security", "find-generic-password",
    "-a", "michaelahern", "-s", "litellm-master-key", "-w"
]).decode().strip()

resp = requests.post(
    "http://127.0.0.1:8092/v1/ocr",
    headers={"Authorization": f"Bearer {master}"},
    json={
        "model": "mistral-ocr",
        "document": {
            "type": "document_url",
            "document_url": "https://arxiv.org/pdf/2201.04234"
        }
    },
    timeout=120,
)
data = resp.json()
print(data["pages"][0]["markdown"])
```

### Curl (test rapide)

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

curl -X POST 'http://127.0.0.1:8092/v1/ocr' \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral-ocr",
    "document": {
      "type": "document_url",
      "document_url": "https://arxiv.org/pdf/2201.04234"
    }
  }'
```

### Document types acceptés

VERIFIE: https://docs.litellm.ai/docs/ocr (section "Accepted Document Types").

| `type`         | Payload                                                      | Cas d'usage                              |
| -------------- | ------------------------------------------------------------ | ---------------------------------------- |
| `document_url` | `{"document_url": "https://..."}` ou data URI                | PDF distant, URL signée S3/GCS           |
| `image_url`    | `{"image_url": "https://..."}` ou data URI                   | Image distante, scan unique              |
| `file`         | `{"file": "/path/to/local.pdf"}` ou bytes/file-object        | Local file upload                        |
| Base64 inline  | `{"document_url": "data:application/pdf;base64,JVBERi0..."}` | PDF inline (privacy : pas d'URL externe) |

Exemple base64 (privacy — aucune URL distante exposée) :

```python
import base64
from pathlib import Path

pdf_bytes = Path("/Users/michaelahern/scan.pdf").read_bytes()
b64 = base64.b64encode(pdf_bytes).decode()

response = ocr(
    model="mistral/mistral-ocr-latest",
    document={
        "type": "document_url",
        "document_url": f"data:application/pdf;base64,{b64}"
    }
)
```

### Paramètres optionnels

VERIFIE: https://docs.litellm.ai/docs/ocr (section "Optional Parameters").

| Param                  | Type       | Effet                                                                         |
| ---------------------- | ---------- | ----------------------------------------------------------------------------- |
| `pages`                | `int[]`    | Restreint l'OCR à un sous-ensemble de pages (0-indexed). Réduit coût/latence. |
| `include_image_base64` | `bool`     | Inclut les images embarquées en base64 dans `response.pages[].images`.        |
| `image_limit`          | `int`      | Plafond nombre d'images extraites par page.                                   |
| `image_min_size`       | `int` (px) | Filtre les images sous ce seuil (logos répétitifs, séparateurs).              |

```python
response = ocr(
    model="mistral/mistral-ocr-latest",
    document={"type": "document_url", "document_url": "https://example.com/doc.pdf"},
    pages=[0, 1, 2],
    include_image_base64=True,
    image_limit=5,
    image_min_size=64,
)
```

### Config YAML — déclarer Mistral OCR dans le proxy

```yaml
# ~/ai-servers/litellm-proxy/config.yaml (à ajouter manuellement, hors scope ce skill)
model_list:
  - model_name: mistral-ocr
    litellm_params:
      model: mistral/mistral-ocr-latest
      api_key: os.environ/MISTRAL_API_KEY
```

> **Note `mode: ocr`** — La doc upstream LiteLLM (https://docs.litellm.ai/docs/ocr) **ne mentionne PAS** de clé `mode` requise dans `model_info` pour `/v1/ocr` (contrairement à `mode: audio_transcription` documenté pour `/audio/transcriptions`). Le code source LiteLLM (`litellm/router.py:_initialize_ocr_search_endpoints`) route via `call_type="ocr"` détecté à partir du chemin URL `/v1/ocr` — pas via `model_info.mode`. STATUT : **NON DOCUMENTÉ upstream**, smoker localement avant de présumer. Si le proxy retourne 404 sur `/v1/ocr` avec config minimale, tester en ajoutant `model_info: { mode: ocr }` comme fallback empirique.

## Section 2 — Pass-through endpoints OCR (locaux/serveur)

Pour OCR locaux (Tesseract, Docling) ou local-only Mac (Apple Vision), LiteLLM expose `general_settings.pass_through_endpoints` qui forward les requêtes vers un backend HTTP. Le proxy garde l'auth master key + cost tracking manuel.

VERIFIE: https://docs.litellm.ai/docs/proxy/pass_through (page upstream récupérée 2026-05-06).

### Config YAML — Tesseract (FastAPI local)

```yaml
# ~/ai-servers/litellm-proxy/config.yaml (à ajouter manuellement, hors scope ce skill)
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  pass_through_endpoints:
    - path: "/ocr/tesseract"
      target: "http://127.0.0.1:9001/ocr" # FastAPI wrapper Tesseract local
      headers:
        content-type: application/json
      forward_headers: false # ne pas leak Authorization vers backend public
      auth: true # exiger master key LiteLLM
      methods: ["POST"]
```

Appel client :

```bash
MASTER=$(security find-generic-password -a "$USER" -s litellm-master-key -w)

curl -X POST 'http://127.0.0.1:8092/ocr/tesseract' \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d '{"image_path": "/tmp/scan.png", "lang": "fra+eng"}'
```

Le wrapper FastAPI local doit exposer `POST /ocr` qui shell-out vers `tesseract <input> stdout -l <lang>` (création hors scope ce skill).

### Config YAML — Docling (docling-serve)

Docling est un parser PDF layout-aware (IBM Research). Image officielle déployable sur VPS arm64 OVH ou local.

```yaml
general_settings:
  pass_through_endpoints:
    - path: "/ocr/docling"
      target: "http://127.0.0.1:5001" # docling-serve port défaut
      headers:
        content-type: application/json
      forward_headers: false
      auth: true
      methods: ["POST"]
```

Appel client (endpoint docling-serve `/v1alpha/convert/source`) :

```bash
curl -X POST 'http://127.0.0.1:8092/ocr/docling/v1alpha/convert/source' \
  -H "Authorization: Bearer $MASTER" \
  -H "Content-Type: application/json" \
  -d '{"http_sources": [{"url": "https://arxiv.org/pdf/2201.04234"}]}'
```

> **VPS-ready** : docling-serve tourne en Docker arm64 sur OVH (image `quay.io/docling-project/docling-serve:latest`). Aligner avec `intellisoins-document-tools` pour skills engine-pure (à venir).

### Config YAML — Apple Vision (ocrmac, local-only)

`ocrmac` wrap le framework Apple Vision via PyObjC. Local-only macOS — **NE PAS déployer sur VPS Linux**.

```yaml
general_settings:
  pass_through_endpoints:
    - path: "/ocr/apple"
      target: "http://127.0.0.1:9002/ocr" # FastAPI wrapper ocrmac local
      headers:
        content-type: application/json
      forward_headers: false
      auth: true
      methods: ["POST"]
```

Wrapper Python local (création hors scope ce skill) :

```python
# ~/ai-servers/ocr-apple/main.py — squelette indicatif
from fastapi import FastAPI
from ocrmac import ocrmac
app = FastAPI()

@app.post("/ocr")
def ocr_apple(payload: dict):
    annotations = ocrmac.OCR(payload["image_path"]).recognize()
    return {"text": "\n".join(a[0] for a in annotations)}
```

> **Anti-pattern** : déployer ce wrapper sur VPS OVH Linux → ImportError PyObjC. Apple Vision n'a pas de port Linux. Garder ce path uniquement sur Mac de Michael.

### Forward headers — quand activer

| `forward_headers` | Comportement                                                | Recommandation                                                                                                               |
| ----------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `false` (défaut)  | Seuls les `headers:` configurés sont envoyés au backend     | **Recommandé** pour backend local public (127.0.0.1) — évite leak `Authorization: Bearer <master>` vers backend si compromis |
| `true`            | Tous les headers client (incluant `Authorization`) propagés | Activer uniquement si backend a besoin de contexte client (end-user-id, custom auth)                                         |

### Cost tracking pass-through

Pas automatique. Ajouter `cost_per_request: 0.0001` (USD) dans la config pour appliquer un coût fixe par appel — ou laisser à `0` et calculer downstream via Langfuse/OTel.

## Configs provider-specific (OCR natif)

### Mistral OCR (cloud EU)

```yaml
- model_name: mistral-ocr
  litellm_params:
    model: mistral/mistral-ocr-latest
    api_key: os.environ/MISTRAL_API_KEY
```

Variantes `mistral-ocr-2503`, `mistral-ocr-latest`. Tarification documentée sur https://mistral.ai/en/pricing — cost tracking auto via LiteLLM.

### Azure AI Document Intelligence

```yaml
- model_name: azure-ocr
  litellm_params:
    model: azure_ai/prebuilt-document
    api_base: os.environ/AZURE_DOC_INTELLIGENCE_ENDPOINT
    api_key: os.environ/AZURE_DOC_INTELLIGENCE_KEY
    api_version: "2024-07-31-preview"
```

NON VERIFIE: forme exacte du `model:` Azure pour `/v1/ocr` LiteLLM (la doc upstream liste Azure comme provider mais ne fournit pas de snippet YAML complet). Smoker avec `litellm.ocr(model="azure_ai/...", ...)` avant de figer ce snippet en config.

### Vertex AI Document AI

```yaml
- model_name: vertex-ocr
  litellm_params:
    model: vertex_ai/document-ai
    vertex_project: os.environ/VERTEX_PROJECT
    vertex_location: os.environ/VERTEX_LOCATION
    vertex_credentials: os.environ/VERTEX_CREDENTIALS
```

NON VERIFIE: même caveat que Azure. La doc liste Vertex comme provider mais sans snippet OCR-specific.

## Fallbacks (OCR natif uniquement)

Pass-through endpoints **n'ont pas** de mécanisme de fallback intégré (pas dans le router LiteLLM). Pour OCR natif :

```python
import requests

resp = requests.post(
    "http://127.0.0.1:8092/v1/ocr",
    headers={"Authorization": f"Bearer {master}"},
    json={
        "model": "mistral-ocr",
        "document": {"type": "document_url", "document_url": "..."},
        "fallbacks": ["azure-ocr", "vertex-ocr"]
    }
)
```

Cf. skill `litellm-routing-fallbacks` pour `mock_testing_fallbacks`, cooldowns, retries.

## Anti-patterns

1. **Hardcoder `MISTRAL_API_KEY`** dans `config.yaml` ou un script Python → utiliser `os.environ/MISTRAL_API_KEY` côté proxy + Keychain pour la master key client.
2. **Encoder le PDF en base64 manuellement quand le SDK accepte un path** → `{"type": "file", "file": "/path/..."}` est plus simple et évite l'OOM sur PDFs >10 MB.
3. **Déployer `ocrmac` sur VPS Linux** → ImportError PyObjC. Apple Vision est macOS-only.
4. **Pass-through sans `auth: true`** sur backend public-facing → bypass complet de la master key LiteLLM, n'importe qui peut hit `/ocr/tesseract` directement via le proxy.
5. **Présumer `mode: ocr` dans `model_info`** sans avoir smoké → la doc upstream ne le documente PAS (contrairement à `mode: audio_transcription`). Tester d'abord la config minimale.
6. **`forward_headers: true` sur backend public ou tier non-trusted** → leak du `Authorization: Bearer <master>` vers le backend si compromis.
7. **Envoyer un PDF patient à `mistral-ocr` sans DPA signé** → violation Loi 25 / PHIPA. Router vers Tesseract/Docling local pour PHI.
8. **Oublier `image_min_size`** sur scans avec watermarks/logos répétés → `response.pages[].images` saturé d'icônes inutiles, payload réseau gonflé.

## Troubleshooting

| Symptôme                                   | Cause probable                                                                              | Fix                                                                                              |
| ------------------------------------------ | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `404 Not Found` sur `/v1/ocr`              | Model `mistral-ocr` absent du `model_list` OU LiteLLM version <= 1.50 (endpoint OCR récent) | Ajouter dans config.yaml + restart proxy + `pip show litellm` (>= 1.55 recommandé)               |
| `401 Unauthorized` côté Mistral            | `MISTRAL_API_KEY` invalide ou révoquée                                                      | `curl https://api.mistral.ai/v1/models -H "Authorization: Bearer $MISTRAL_API_KEY"` pour valider |
| `400 Bad Request` "document required"      | JSON mal formé : `document` doit être un objet, pas une string                              | `{"document": {"type": "document_url", "document_url": "..."}}`, pas `{"document": "..."}`       |
| Pass-through `/ocr/tesseract` retourne 502 | Backend FastAPI DOWN sur 127.0.0.1:9001                                                     | Démarrer le wrapper local, vérifier `lsof -iTCP:9001`                                            |
| Réponse Mistral OCR vide pour PDF scanné   | PDF en image rasterisée + Mistral n'extrait pas → utiliser engine OCR (vs PDF parser)       | Réessayer avec `tesseract` ou `docling` (layout-aware)                                           |
| `image_limit` ignoré                       | Param non supporté par le provider (Vertex notamment)                                       | Filtrer côté client après réception                                                              |
| Cost tracking absent dans Admin UI         | Pass-through sans `cost_per_request`                                                        | Ajouter `cost_per_request: 0.0001` dans la config pass-through                                   |

## Cross-references

| Skill                                          | Quand consulter                                                                     |
| ---------------------------------------------- | ----------------------------------------------------------------------------------- |
| `litellm-config-yaml`                          | Référence complète `model_list` / `model_info` / `general_settings`                 |
| `litellm-routing-fallbacks`                    | Fallbacks, cooldowns, retries, A/B testing OCR                                      |
| `litellm-providers-models`                     | Liste exhaustive Mistral/Azure/Vertex modèles OCR                                   |
| `litellm-guardrails-policies`                  | Presidio sur sortie OCR (PII patient, NAS, dates) — Loi 25                          |
| `litellm-logging-metrics`                      | Trace Langfuse/OTel pour requêtes `/ocr`                                            |
| `litellm-audio-transcriptions`                 | Pattern voisin (`mode: audio_transcription`, multipart, fallbacks)                  |
| `intellisoins-infrastructure:local-ai-servers` | Gestion `aictl` pour démarrer wrappers OCR locaux                                   |
| `intellisoins-document-tools:*`                | Skills engine-pure futurs (Tesseract/Docling/Apple Vision standalone, sans LiteLLM) |

Rules :

- `~/.claude/rules/local-ai-stack.md` — proxy port 8092, Keychain, master key pattern subprocess
- `~/ai-servers/litellm-proxy/config.yaml` — config proxy actuelle (à modifier manuellement, hors scope skill)

Docs upstream :

- https://docs.litellm.ai/docs/ocr — endpoint `/v1/ocr` natif (Mistral/Azure/Vertex)
- https://docs.litellm.ai/docs/proxy/pass_through — `general_settings.pass_through_endpoints`
- https://docling-project.github.io/docling/ — Docling parser PDF layout-aware
- https://github.com/straussmaximilian/ocrmac — Apple Vision wrapper Python
- https://tesseract-ocr.github.io/ — Tesseract OCR engine

## Endpoints connexes (hors scope de ce skill)

- `/v1/embeddings` — embeddings texte/image (cf. skill `litellm-rag-ingest`)
- `/v1/rerank` — reranking (cf. skill `litellm-rerank`)
- Engine-pure OCR (sans LiteLLM) — à couvrir dans `intellisoins-document-tools` quand les skills Tesseract/Docling/Apple Vision standalone seront créés.
