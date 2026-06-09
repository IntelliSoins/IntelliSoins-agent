# Signal Agent Router

Local-only Signal Messenger channel for Michael's personal read-only agent.

## Services

- `signal-api` listens on `127.0.0.1:8094` and runs `bbernhard/signal-cli-rest-api` in Docker.
- `signal-agent-router` listens on `127.0.0.1:8096`, polls allowed Signal senders, calls LiteLLM on `127.0.0.1:8092`, and replies in Signal.
- SignalWire/SMS remains parallel through `SIGNALWIRE_NOTIFY_URL` or `SMS_WORKER_URL`.

WireGuard is not required for this Mac-local v1. Add WG only if the router moves to a VPS or another machine needs to call local Mac endpoints.

## Local Config

Create `~/ai-servers/signal-agent-router/.env` locally:

```bash
SIGNAL_ACCOUNT_NUMBER=+15551234567
SIGNAL_ALLOWED_SENDERS=+15557654321
SIGNAL_NOTIFICATION_RECIPIENTS=+15557654321

SIGNAL_API_MODE=native
SIGNAL_API_PORT=8094
SIGNAL_ROUTER_PORT=8096

LITELLM_MODEL=qwen35-9b-vision
LITELLM_API_BASE=http://127.0.0.1:8092/v1

# Optional read-only context adapters. Use absolute commands where possible.
# SIGNAL_AGENT_TASKS_COMMAND=/path/to/tasks-summary
# SIGNAL_AGENT_EMAIL_COMMAND=/path/to/email-summary
# SIGNAL_AGENT_CALENDAR_COMMAND=/path/to/calendar-summary

# Optional SignalWire/SMS fallback.
# SMS_WORKER_URL=https://example.workers.dev/sms/notify-owner
# SMS_ADMIN_TOKEN=...
```

Secrets and Signal state are intentionally outside Git. The Signal API stores device keys in `${SIGNAL_API_CONFIG_DIR:-$HOME/.local/share/signal-api}`.

## Setup

```bash
./aictl install
./aictl start signal-api
open "http://127.0.0.1:8094/v1/qrcodelink?device_name=signal-agent"
```

Scan the QR code in Signal: Settings -> Linked devices -> Link new device.

Then start the router:

```bash
./aictl start signal-agent-router
curl -s http://127.0.0.1:8096/health | python3 -m json.tool
```

## Notify API

Local tools can send a summary to Signal and SignalWire in parallel:

```bash
curl -s http://127.0.0.1:8096/notify \
  -H 'Content-Type: application/json' \
  -d '{"message":"Résumé local: rien d urgent.","channels":["signal","signalwire"]}'
```

The interactive Signal route is read-only in v1. Requests that imply mutations should return a proposed action, not execute it.
