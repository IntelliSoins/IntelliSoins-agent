---
paths:
  - "**/litellm*realtime*"
  - "**/realtime*litellm*"
  - "**/websocket*audio*"
---

# LiteLLM `/v1/realtime` — WebSocket + WebRTC

Endpoint Realtime API d'OpenAI exposé via LiteLLM en **deux modes** complémentaires :

- **WebSocket** `/v1/realtime` — server-to-server (agents vocaux backend, transcription continue). Audio passe par le proxy.
- **WebRTC** `/v1/realtime/client_secrets` + `/v1/realtime/calls` — browser/mobile (latence minimale). LiteLLM ne sert que d'**autorité de tokens et relais SDP** ; l'audio est en P2P direct entre le client et le provider.

Le choix entre les deux dépend de **où vit le client audio** : un serveur Python qui consomme un flux mic d'une app interne → WebSocket. Une PWA Next.js qui appelle directement OpenAI depuis le navigateur de l'utilisateur → WebRTC.

## Matrice des features

| Feature           | WebSocket                                              | WebRTC                                                             |
| ----------------- | ------------------------------------------------------ | ------------------------------------------------------------------ |
| Topologie         | Client ↔ LiteLLM ↔ Provider                            | Client ↔ LiteLLM (token + SDP), audio P2P direct Client ↔ Provider |
| Latence audio     | + 1 hop (relai proxy)                                  | Minimal (P2P)                                                      |
| Cas d'usage       | Agent serveur, transcription continue, voice-bot S2S   | Browser/mobile UI, voice chat utilisateur final                    |
| Providers         | OpenAI, Azure, xAI, Gemini, Vertex, Bedrock            | OpenAI, Azure                                                      |
| Auth client       | `Authorization: Bearer sk-litellm` ou `api-key` header | Token éphémère encrypté (`ek_...`) issu de `client_secrets`        |
| Cost tracking     | ✓                                                      | ✓ (côté LiteLLM via session events)                                |
| Logging callbacks | ✓ Langfuse/OTel/Datadog (`litellm-logging-metrics`)    | ✓ (events captés via data channel relay)                           |
| Guardrails        | ✓ Virtual key / team / query param                     | ⚠ Limité (audio P2P bypasse le proxy)                              |
| Fallbacks         | Hérités du config.yaml                                 | Encodés dans le token                                              |

## Setup config.yaml — modèles realtime

`mode: realtime` dans `model_info` est obligatoire pour que LiteLLM route le modèle vers les endpoints WebSocket et WebRTC.

```yaml
model_list:
  # OpenAI
  - model_name: openai-gpt-4o-realtime-audio
    litellm_params:
      model: openai/gpt-4o-realtime-preview-2024-12-17
      api_key: os.environ/OPENAI_API_KEY
    model_info:
      mode: realtime

  # Azure (api_version + api_base requis)
  - model_name: azure-gpt-4o-realtime
    litellm_params:
      model: azure/gpt-4o-realtime-preview
      api_key: os.environ/AZURE_SWEDEN_API_KEY
      api_base: os.environ/AZURE_SWEDEN_API_BASE
      api_version: "2024-10-01-preview"
    model_info:
      mode: realtime

  # xAI Grok voice agent
  - model_name: grok-voice-agent
    litellm_params:
      model: xai/grok-4-1-fast-non-reasoning
      api_key: os.environ/XAI_API_KEY
    model_info:
      mode: realtime
```

Démarrer le proxy :

```bash
litellm --config /path/to/config.yaml
```

Providers supplémentaires supportés : **Google AI Studio (Gemini)**, **Vertex AI**, **Bedrock**. Même structure `mode: realtime`, paramètres provider-specific selon `litellm-providers-models`.

## Mode WebSocket — server-to-server

### Architecture

```
Server (Python/Node)         LiteLLM Proxy            OpenAI/Azure/xAI
        |                           |                          |
        |== ws ====================>|== ws ===================>|
        |                           |                          |
        |<= audio events ===========|<= audio events ==========|
```

Le proxy relaie tous les frames WebSocket dans les deux sens. Audio, événements, transcripts passent **tous** par le proxy (point de capture pour cost tracking, logging, guardrails).

### Connexion Python

```python
import asyncio
import json
import websockets

async def main():
    url = "ws://0.0.0.0:4000/v1/realtime?model=openai-gpt-4o-realtime-audio"
    async with websockets.connect(
        url,
        additional_headers={"Authorization": "Bearer sk-1234"}
    ) as ws:
        print("Connected")
        await ws.send(json.dumps({
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
                "instructions": "Réponds en français québécois."
            }
        }))
        async for msg in ws:
            data = json.loads(msg)
            if data["type"] == "error":
                print("Blocked:", data["error"]["message"])
                break
            print(data)

asyncio.run(main())
```

### Connexion Node.js

```javascript
const WebSocket = require("ws");
const url = "ws://0.0.0.0:4000/v1/realtime?model=openai-gpt-4o-realtime-audio";

const ws = new WebSocket(url, {
  headers: {
    "api-key": "sk-1234",
    "OpenAI-Beta": "realtime=v1",
  },
});

ws.on("open", () => {
  console.log("Connected to server.");
  ws.send(
    JSON.stringify({
      type: "response.create",
      response: {
        modalities: ["text"],
        instructions: "Please assist the user.",
      },
    }),
  );
});

ws.on("message", (message) => {
  console.log(JSON.parse(message.toString()));
});

ws.on("error", (error) => {
  console.error("Error: ", error);
});
```

### Auth — `Authorization: Bearer` vs `api-key` header

Les deux sont acceptés. `Authorization: Bearer sk-...` est l'OpenAI-style standard ; `api-key: sk-...` est l'Azure-style. Inclure `OpenAI-Beta: realtime=v1` quand le client SDK l'attend (clients Node WebSocket basés sur OpenAI SDK).

### Events session (extrait OpenAI Realtime API)

Le payload texte/JSON suit la spec OpenAI Realtime. Events fréquents côté client→serveur :

| Event                       | Rôle                                                                      |
| --------------------------- | ------------------------------------------------------------------------- |
| `session.update`            | Modifier instructions, voice, temperature, modalities en cours de session |
| `input_audio_buffer.append` | Ajouter un chunk PCM16 base64 au buffer mic                               |
| `input_audio_buffer.commit` | Forcer la commit du buffer (mode push-to-talk)                            |
| `conversation.item.create`  | Injecter un message texte dans la conversation                            |
| `response.create`           | Demander une réponse (texte + audio selon modalities)                     |
| `response.cancel`           | Annuler une réponse en cours                                              |

Events serveur→client : `session.created`, `response.created`, `response.audio.delta`, `response.text.delta`, `response.done`, `error`. Voir spec OpenAI pour la liste complète — LiteLLM passe les événements **transparents**.

## Mode WebRTC — browser/mobile

### Architecture

```
Browser                  LiteLLM Proxy              OpenAI/Azure
  |                           |                          |
  |-- POST client_secrets --->|-- POST sessions -------->|
  |<-- encrypted_token -------|<-- ek_... ---------------|
  |                           |                          |
  |-- POST calls [SDP+token] ->|-- POST calls ----------->|
  |<-- SDP answer ------------|<-- SDP answer -----------|
  |                           |                          |
  |===== audio P2P direct =================================|
```

Trois propriétés clés :

1. **L'audio ne passe PAS par le proxy.** Une fois la handshake SDP complétée, le browser parle directement au provider via UDP/SRTP. La latence est minimale et la bande passante du serveur LiteLLM n'est pas consommée par les flux audio.
2. **Le token encrypté `ek_...` est éphémère** (quelques minutes). Il faut en générer un juste avant `RTCPeerConnection.createOffer()` ; sinon 401 token expired.
3. **Le `model` est encodé dans le token.** Ne PAS passer `?model=...` dans `/v1/realtime/calls` — la route est déterminée par le token.

### Étape 1 — Obtenir un token éphémère

```javascript
const r = await fetch("http://proxy:4000/v1/realtime/client_secrets", {
  method: "POST",
  headers: {
    Authorization: "Bearer sk-litellm-key",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ model: "openai-gpt-4o-realtime-audio" }),
});
const { client_secret } = await r.json();
const token = client_secret.value; // "ek_..."
```

LiteLLM appelle `POST /v1/realtime/sessions` côté provider, retourne le token encrypté. Le `model_name` (`openai-gpt-4o-realtime-audio`) doit correspondre à un entry `model_list` avec `mode: realtime`.

### Étape 2 — Handshake WebRTC + SDP

```javascript
// Setup peer connection + audio
const pc = new RTCPeerConnection();
const audio = document.createElement("audio");
audio.autoplay = true;
pc.ontrack = (e) => (audio.srcObject = e.streams[0]);

// Mic local
const ms = await navigator.mediaDevices.getUserMedia({ audio: true });
pc.addTrack(ms.getTracks()[0]);

// Data channel pour les events (texte JSON)
const dc = pc.createDataChannel("oai-events");

// Génération de l'offer SDP
const offer = await pc.createOffer();
await pc.setLocalDescription(offer);

// Envoi de l'offer SDP au proxy avec le token éphémère
const sdpRes = await fetch("http://proxy:4000/v1/realtime/calls", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/sdp",
  },
  body: offer.sdp,
});

// SDP answer du provider, relayé par LiteLLM
await pc.setRemoteDescription({
  type: "answer",
  sdp: await sdpRes.text(),
});
```

Le `Bearer ${token}` ici est l'**`ek_...` éphémère**, pas la clé LiteLLM. Confondre les deux est l'erreur 401 la plus fréquente.

### Étape 3 — Events via data channel

```javascript
dc.onopen = () => {
  // Customiser la session après handshake
  dc.send(
    JSON.stringify({
      type: "session.update",
      session: {
        instructions: "Tu es un assistant pharmacien. Réponds en français québécois.",
        voice: "alloy",
        modalities: ["audio", "text"],
      },
    }),
  );
};

dc.onmessage = (e) => {
  const event = JSON.parse(e.data);
  if (event.type === "response.text.delta") {
    console.log("Δtext:", event.delta);
  }
};
```

Les events serveur arrivent via `dc.onmessage` (data channel), l'audio arrive via `pc.ontrack` (track audio remote). Les deux canaux sont indépendants.

### Spécificités Azure WebRTC

Pour Azure, le `model_list` doit pointer vers `azure/gpt-4o-realtime-preview` avec `api_base`, `api_key`, **et** `api_version` correctement renseignés. La plupart des 401/500 inattendus en mode WebRTC Azure viennent d'un `api_version` manquant ou d'un `api_base` qui pointe vers la mauvaise région.

```yaml
- model_name: azure-realtime-prod
  litellm_params:
    model: azure/gpt-4o-realtime-preview
    api_key: os.environ/AZURE_SWEDEN_API_KEY
    api_base: os.environ/AZURE_SWEDEN_API_BASE
    api_version: "2024-10-01-preview"
  model_info:
    mode: realtime
```

## Sécurité — virtual keys, guardrails, rate limits

### Virtual keys

Comme tout endpoint LiteLLM, l'auth se fait via virtual keys (cf. `litellm-authentication`). Pour WebRTC, **ne jamais exposer la master key au browser** — toujours un workflow :

1. Backend : génère une virtual key courte-durée par session utilisateur (`/key/generate` avec TTL).
2. Backend : appelle `/v1/realtime/client_secrets` avec cette virtual key.
3. Backend : retourne uniquement le `client_secret.value` (`ek_...`) au browser.
4. Browser : utilise `ek_...` pour `/v1/realtime/calls`.

Le browser ne voit **jamais** la virtual key ni la master key.

### Guardrails

- **WebSocket** : `&guardrails=ma-guardrail` en query param OU configuré sur la virtual key/team. Bloque côté proxy avec un event WebSocket `{"type": "error", "error": {"type": "guardrail_error", "message": "..."}}`.
- **WebRTC** : Limité — l'audio P2P bypasse le proxy. Les guardrails sur events texte (data channel) sont moins systématiques. Pour cas pharmacie/Loi 25 sensibles, privilégier WebSocket + guardrail Presidio (cf. `litellm-guardrails-policies`).

### Rate limits & budgets

`max_parallel_requests`, `tpm_limit`, `rpm_limit` s'appliquent à `/v1/realtime` et `/v1/realtime/client_secrets` comme à tout endpoint (cf. `litellm-budgets-spend`). Une session WebRTC longue compte comme une seule requête côté `client_secrets` mais la consommation tokens est mesurée via les events `response.done`.

## Logging & cost tracking

Par défaut, LiteLLM log uniquement trois types d'events : `session.created`, `response.create`, `response.done`. Override via `logged_real_time_event_types` dans `litellm_settings` :

```yaml
litellm_settings:
  logged_real_time_event_types:
    - session.created
    - session.update
    - response.create
    - response.audio.delta # verbeux
    - response.done
    - error
```

Les events sont propagés aux callbacks Langfuse, OpenTelemetry, Datadog, Arize (cf. `litellm-logging-metrics`). Pour Langfuse, chaque session realtime apparaît comme une trace avec spans pour chaque `response.*`.

Cost tracking : LiteLLM mesure les tokens audio (input + output) via les events `response.done` qui contiennent `usage.input_tokens` et `usage.output_tokens` ventilés par modalité. Visible via `/spend/logs` et l'Admin UI.

## FAQ

| Symptôme                        | Cause                                         | Action                                                                                          |
| ------------------------------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `401 token expired`             | Token `ek_...` généré trop tôt                | Générer juste avant `pc.createOffer()` ; ne jamais réutiliser                                   |
| `401 Unauthorized` sur `/calls` | Bearer = master key au lieu de `ek_...`       | Utiliser le token encrypté retourné par `/v1/realtime/client_secrets`                           |
| `model not found` sur `/calls`  | Tentative de passer `?model=...` à `/calls`   | Ne PAS passer model — il est encodé dans le token                                               |
| Pas d'audio entrant             | `pc.ontrack` non configuré ou autoplay bloqué | `audio.autoplay = true` + `audio.srcObject = e.streams[0]`                                      |
| Pas d'audio sortant             | Permissions mic refusées                      | `navigator.mediaDevices.getUserMedia({audio:true})` doit succeed                                |
| 500 sur Azure                   | `api_version` manquant                        | Ajouter `api_version: "2024-10-01-preview"` dans `litellm_params`                               |
| Connexion freeze                | Firewall WebRTC (UDP)                         | Vérifier UDP sortant + STUN/TURN si NAT strict                                                  |
| `guardrail_error`               | Politique bloquée                             | Inspecter `guardrails` sur la virtual key (`/key/info`)                                         |
| Logs vides                      | `logged_real_time_event_types` non configuré  | Ajouter les events voulus dans `litellm_settings`                                               |
| Stream s'arrête après ~5min     | Token éphémère expiré pendant session longue  | Pour sessions longues, prévoir `session.update` avec re-auth (pattern à valider selon provider) |

## Limitations actuelles (mai 2026)

- **WebRTC providers** : OpenAI + Azure seulement. xAI/Gemini/Vertex/Bedrock sont WebSocket-only pour l'instant.
- **Streaming guardrails côté audio P2P** : non disponible (l'audio bypasse le proxy par design).
- **Cost tracking pour audio long** : précision dépend des events `response.done` du provider — vérifier la cohérence avec la facturation provider sur sessions > 1h.
- **No SDK Python natif `litellm.arealtime`** : pour Python, utiliser `websockets` directement (cf. exemple ci-dessus). Si un SDK abstraction est ajouté, voir release notes LiteLLM.

## Cross-références

- [`litellm-config-yaml`](../litellm-config-yaml/SKILL.md) — référence complète `model_list`, `model_info.mode`, `litellm_settings`
- [`litellm-proxy-setup`](../litellm-proxy-setup/SKILL.md) — démarrage proxy, Docker, Admin UI
- [`litellm-authentication`](../litellm-authentication/SKILL.md) — virtual keys, master key, génération de clés courte-durée
- [`litellm-providers-models`](../litellm-providers-models/SKILL.md) — config provider-specific (OpenAI, Azure, xAI, Gemini, Vertex, Bedrock)
- [`litellm-guardrails-policies`](../litellm-guardrails-policies/SKILL.md) — Presidio, Lakera, Aporia pour PII/Loi 25
- [`litellm-logging-metrics`](../litellm-logging-metrics/SKILL.md) — Langfuse, OTel, Datadog, `logged_real_time_event_types`
- [`litellm-budgets-spend`](../litellm-budgets-spend/SKILL.md) — rate limits, budgets per-key/team
- [`litellm-routing-fallbacks`](../litellm-routing-fallbacks/SKILL.md) — fallbacks model si `/v1/realtime` échoue
- [`litellm-audio-speech`](../litellm-audio-speech/SKILL.md) — TTS one-shot (alternative async pour cas non-realtime)
- [`litellm-audio-transcriptions`](../litellm-audio-transcriptions/SKILL.md) — STT one-shot (alternative pour fichiers audio)

## Anti-patterns

- **Ne PAS** exposer la master key ou virtual key au browser. Toujours backend → `client_secrets` → `ek_...` → browser.
- **Ne PAS** réutiliser un `ek_...` entre sessions ou utilisateurs. Token éphémère = un par WebRTC session.
- **Ne PAS** passer `?model=...` à `/v1/realtime/calls`. Le routing est encodé dans le token.
- **Ne PAS** activer `response.audio.delta` dans les logs en prod sans throttling — extrêmement verbeux (10-100 events/s).
- **Ne PAS** utiliser WebRTC pour cas Loi 25 sensibles sans audit dédié — l'audio P2P contourne les guardrails proxy.
- **Ne PAS** confondre `/v1/realtime` (WebSocket) avec `/v1/realtime/calls` (WebRTC SDP). Les deux endpoints existent et servent à des choses différentes.

## Sources

- LiteLLM docs `/realtime` : https://docs.litellm.ai/docs/realtime
- LiteLLM blog "Realtime WebRTC HTTP Endpoints" (12 mars 2026) : https://docs.litellm.ai/blog/realtime_webrtc_http_endpoints
- OpenAI Realtime API spec : https://platform.openai.com/docs/api-reference/realtime
