#!/usr/bin/env python3
"""Local Signal Messenger router for read-only personal-agent replies."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("SIGNAL_AGENT_ROOT", "/Users/michaelahern/ai-servers"))


def _bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _csv(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


def _json_dumps(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def log(message: str) -> None:
    print(f"[signal-agent-router] {message}", flush=True)


def keychain_secret(service: str) -> str:
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""), "-s", service, "-w"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


@dataclass(frozen=True)
class Config:
    host: str = os.environ.get("SIGNAL_ROUTER_HOST", "127.0.0.1")
    port: int = int(os.environ.get("SIGNAL_ROUTER_PORT", "8096"))
    signal_api_base: str = os.environ.get("SIGNAL_API_BASE", "http://127.0.0.1:8094").rstrip("/")
    account_number: str = os.environ.get("SIGNAL_ACCOUNT_NUMBER", "").strip()
    allowed_senders: tuple[str, ...] = tuple(_csv("SIGNAL_ALLOWED_SENDERS"))
    notification_recipients: tuple[str, ...] = tuple(_csv("SIGNAL_NOTIFICATION_RECIPIENTS"))
    allow_groups: bool = _bool("SIGNAL_ALLOW_GROUPS", False)
    poll_interval: float = float(os.environ.get("SIGNAL_POLL_INTERVAL_SECONDS", "10"))
    state_path: Path = Path(
        os.environ.get(
            "SIGNAL_AGENT_STATE_PATH",
            str(Path.home() / "Library/Application Support/ai-servers/signal-agent-router/state.json"),
        )
    )
    dry_run: bool = _bool("SIGNAL_AGENT_DRY_RUN", False)
    litellm_api_base: str = os.environ.get("LITELLM_API_BASE", "http://127.0.0.1:8092/v1").rstrip("/")
    litellm_model: str = os.environ.get("LITELLM_MODEL", "qwen35-9b-vision")
    litellm_api_key: str = os.environ.get("SIGNAL_AGENT_LITELLM_API_KEY") or os.environ.get("LITELLM_API_KEY") or ""
    litellm_keychain_service: str = os.environ.get("SIGNAL_AGENT_LITELLM_KEYCHAIN_SERVICE", "litellm-master-key")
    command_timeout: int = int(os.environ.get("SIGNAL_AGENT_COMMAND_TIMEOUT_SECONDS", "20"))
    max_context_chars: int = int(os.environ.get("SIGNAL_AGENT_MAX_CONTEXT_CHARS", "16000"))
    signalwire_notify_url: str = os.environ.get("SIGNALWIRE_NOTIFY_URL") or os.environ.get("SMS_WORKER_URL", "")
    signalwire_admin_token: str = os.environ.get("SIGNALWIRE_ADMIN_TOKEN") or os.environ.get("SMS_ADMIN_TOKEN", "")
    admin_token: str = os.environ.get("SIGNAL_AGENT_ADMIN_TOKEN", "")

    def api_key(self) -> str:
        return self.litellm_api_key or keychain_secret(self.litellm_keychain_service)

    def default_recipients(self) -> tuple[str, ...]:
        return self.notification_recipients or self.allowed_senders


CONFIG = Config()


class State:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.processed: list[str] = []
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        self.processed = [str(item) for item in data.get("processed", [])][-500:]

    def seen(self, key: str) -> bool:
        with self.lock:
            return key in self.processed

    def mark(self, key: str) -> None:
        with self.lock:
            if key in self.processed:
                return
            self.processed.append(key)
            self.processed = self.processed[-500:]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"processed": self.processed}, indent=2), encoding="utf-8")


STATE = State(CONFIG.state_path)


def http_json(method: str, url: str, payload: Any | None = None, headers: dict[str, str] | None = None, timeout: int = 20) -> Any:
    body = None if payload is None else _json_dumps(payload)
    request_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} -> HTTP {exc.code}: {raw[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{method} {url} -> {exc.reason}") from exc


def receive_messages() -> list[dict[str, Any]]:
    if not CONFIG.account_number:
        return []
    number = urllib.parse.quote(CONFIG.account_number, safe="")
    url = f"{CONFIG.signal_api_base}/v1/receive/{number}"
    data = http_json("GET", url, timeout=25)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        messages = data.get("messages") or data.get("envelopes") or []
        if isinstance(messages, list):
            return [item for item in messages if isinstance(item, dict)]
    return []


def extract_message(item: dict[str, Any]) -> dict[str, Any] | None:
    envelope = item.get("envelope") if isinstance(item.get("envelope"), dict) else item
    data_message = envelope.get("dataMessage") if isinstance(envelope.get("dataMessage"), dict) else {}
    sync_message = envelope.get("syncMessage") if isinstance(envelope.get("syncMessage"), dict) else {}
    sent_message = sync_message.get("sentMessage") if isinstance(sync_message.get("sentMessage"), dict) else {}

    if sent_message:
        return None

    text = data_message.get("message") or envelope.get("message") or ""
    text = str(text).strip()
    if not text:
        return None

    group_info = data_message.get("groupInfo") if isinstance(data_message.get("groupInfo"), dict) else {}
    group_id = str(group_info.get("groupId") or group_info.get("groupIdBase64") or "")
    if group_id and not CONFIG.allow_groups:
        return None

    source = str(
        envelope.get("sourceNumber")
        or envelope.get("source")
        or envelope.get("sourceUuid")
        or envelope.get("sourceName")
        or ""
    ).strip()
    source_uuid = str(envelope.get("sourceUuid") or "").strip()
    timestamp = str(data_message.get("timestamp") or envelope.get("timestamp") or item.get("timestamp") or "")

    if not source or source == CONFIG.account_number:
        return None

    digest = hashlib.sha256(f"{timestamp}|{source}|{source_uuid}|{group_id}|{text}".encode("utf-8")).hexdigest()
    return {
        "key": digest,
        "source": source,
        "source_uuid": source_uuid,
        "text": text,
        "timestamp": timestamp,
        "group_id": group_id,
    }


def sender_allowed(message: dict[str, Any]) -> bool:
    allowed = set(CONFIG.allowed_senders)
    return message["source"] in allowed or message.get("source_uuid") in allowed


def classify_intent(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("statut", "status", "serveur", "aictl", "health")):
        return "status"
    if any(word in lowered for word in ("agenda", "calendrier", "calendar", "evenement", "événement")):
        return "calendar"
    if any(word in lowered for word in ("courriel", "courriels", "email", "mail")):
        return "email"
    if any(word in lowered for word in ("tache", "tâche", "task", "todo", "rappel")):
        return "tasks"
    if any(word in lowered for word in ("resume", "résumé", "summary", "brief", "bilan")):
        return "summary"
    return "chat"


def run_command(name: str, command: str) -> str:
    if not command:
        return f"[{name}] Non configure."
    try:
        args = shlex.split(command)
    except ValueError as exc:
        return f"[{name}] Commande invalide: {exc}"
    if not args:
        return f"[{name}] Non configure."
    try:
        result = subprocess.run(
            args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=CONFIG.command_timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"[{name}] Echec: {exc}"
    output = (result.stdout + ("\n" + result.stderr if result.stderr else "")).strip()
    if not output:
        output = f"Commande terminee avec code {result.returncode}, sans sortie."
    return f"[{name}] code={result.returncode}\n{output}"


def context_for_intent(intent: str) -> str:
    providers: list[tuple[str, str]] = []
    if intent in {"status", "summary"}:
        providers.append(("status", os.environ.get("SIGNAL_AGENT_STATUS_COMMAND", str(ROOT / "aictl") + " status")))
    if intent in {"calendar", "summary"}:
        providers.append(("calendar", os.environ.get("SIGNAL_AGENT_CALENDAR_COMMAND", "")))
    if intent in {"email", "summary"}:
        providers.append(("email", os.environ.get("SIGNAL_AGENT_EMAIL_COMMAND", "")))
    if intent in {"tasks", "summary"}:
        providers.append(("tasks", os.environ.get("SIGNAL_AGENT_TASKS_COMMAND", "")))
    if intent == "status":
        providers.append(("health", os.environ.get("SIGNAL_AGENT_HEALTH_COMMAND", str(ROOT / "aictl") + " health")))

    chunks = [run_command(name, command) for name, command in providers]
    context = "\n\n".join(chunks)
    return context[: CONFIG.max_context_chars]


def build_prompt(source: str, text: str, intent: str, context: str) -> list[dict[str, str]]:
    system = (
        "Tu es l'agent personnel local de Michael sur son Mac. "
        "Tu reponds en francais quebecois naturel, court et concret. "
        "Le mode v1 est lecture seule: ne promets aucune modification, suppression, envoi externe ou action calendrier. "
        "Si une source de donnees est non configuree, dis-le clairement au lieu d'inventer. "
        "Pour les demandes d'action, prepare seulement une suggestion et demande de passer par un canal d'execution separe."
    )
    user = (
        f"Canal: Signal Messenger\n"
        f"Expediteur: {source}\n"
        f"Intention detectee: {intent}\n"
        f"Message:\n{text}\n\n"
        f"Contexte local disponible:\n{context or '[aucun contexte local ajoute]'}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def llm_reply(source: str, text: str) -> str:
    intent = classify_intent(text)
    context = context_for_intent(intent)
    api_key = CONFIG.api_key()
    if not api_key:
        return "Je recois le message, mais la cle LiteLLM locale est absente. Verifie le Keychain `litellm-master-key` ou SIGNAL_AGENT_LITELLM_API_KEY."

    payload = {
        "model": CONFIG.litellm_model,
        "messages": build_prompt(source, text, intent, context),
        "temperature": 0.2,
        "max_tokens": 700,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        data = http_json("POST", f"{CONFIG.litellm_api_base}/chat/completions", payload, headers=headers, timeout=60)
        content = data["choices"][0]["message"]["content"]
        return str(content).strip()[:3500]
    except Exception as exc:  # keep Signal replies useful even when the model route is down.
        log(f"LiteLLM error: {exc}")
        if context:
            return f"Le routeur est vivant, mais l'appel LiteLLM a echoue. Contexte brut:\n{context[:2500]}"
        return "Le routeur est vivant, mais l'appel LiteLLM a echoue et aucun contexte local n'etait disponible."


def send_signal(message: str, recipients: list[str]) -> dict[str, Any]:
    if CONFIG.dry_run:
        log(f"dry-run Signal send to {recipients}: {message[:120]}")
        return {"dry_run": True, "recipients": recipients}
    if not CONFIG.account_number:
        raise RuntimeError("SIGNAL_ACCOUNT_NUMBER manquant")
    payload = {"message": message, "number": CONFIG.account_number, "recipients": recipients}
    return http_json("POST", f"{CONFIG.signal_api_base}/v2/send", payload, timeout=30)


def send_signalwire(message: str) -> dict[str, Any]:
    if not CONFIG.signalwire_notify_url:
        return {"skipped": "SIGNALWIRE_NOTIFY_URL/SMS_WORKER_URL non configure"}
    headers: dict[str, str] = {}
    if CONFIG.signalwire_admin_token:
        headers["Authorization"] = f"Bearer {CONFIG.signalwire_admin_token}"
        headers["X-Admin-Token"] = CONFIG.signalwire_admin_token
    payload = {"message": message, "source": "signal-agent-router"}
    return http_json("POST", CONFIG.signalwire_notify_url, payload, headers=headers, timeout=20)


def process_incoming(message: dict[str, Any]) -> None:
    if STATE.seen(message["key"]):
        return
    STATE.mark(message["key"])

    if not sender_allowed(message):
        log(f"ignored non-allowlisted sender {message['source']}")
        return

    reply = llm_reply(message["source"], message["text"])
    send_signal(reply, [message["source"]])
    log(f"replied to {message['source']}")


def poll_loop() -> None:
    last_config_warning = 0.0
    while True:
        if not CONFIG.account_number or not CONFIG.allowed_senders:
            now = time.time()
            if now - last_config_warning > 60:
                log("waiting for SIGNAL_ACCOUNT_NUMBER and SIGNAL_ALLOWED_SENDERS")
                last_config_warning = now
            time.sleep(CONFIG.poll_interval)
            continue
        try:
            for item in receive_messages():
                message = extract_message(item)
                if message:
                    process_incoming(message)
        except Exception as exc:
            log(f"poll error: {exc}")
        time.sleep(CONFIG.poll_interval)


class Handler(BaseHTTPRequestHandler):
    server_version = "SignalAgentRouter/0.1"

    def _send(self, status: int, data: Any) -> None:
        body = _json_dumps(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _authorized(self) -> bool:
        if not CONFIG.admin_token:
            return self.client_address[0] in {"127.0.0.1", "::1"}
        auth = self.headers.get("Authorization", "")
        token = self.headers.get("X-Agent-Token", "")
        return auth == f"Bearer {CONFIG.admin_token}" or token == CONFIG.admin_token

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self._send(404, {"error": "not_found"})
            return
        signal_api = "unknown"
        try:
            http_json("GET", f"{CONFIG.signal_api_base}/v1/health", timeout=2)
            signal_api = "ok"
        except Exception as exc:
            signal_api = f"unreachable: {exc}"
        self._send(
            200,
            {
                "status": "ok",
                "mode": "read_only",
                "signal_api": signal_api,
                "account_configured": bool(CONFIG.account_number),
                "allowed_senders": len(CONFIG.allowed_senders),
                "litellm_base": CONFIG.litellm_api_base,
                "litellm_model": CONFIG.litellm_model,
                "dry_run": CONFIG.dry_run,
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/notify":
            self._send(404, {"error": "not_found"})
            return
        if not self._authorized():
            self._send(401, {"error": "unauthorized"})
            return
        try:
            data = self._json_body()
            message = str(data.get("message") or "").strip()
            if not message:
                raise ValueError("message is required")
            channels = data.get("channels") or ["signal", "signalwire"]
            if not isinstance(channels, list):
                raise ValueError("channels must be a list")

            result: dict[str, Any] = {}
            if "signal" in channels:
                recipients = data.get("recipients") or list(CONFIG.default_recipients())
                if not isinstance(recipients, list) or not recipients:
                    raise ValueError("Signal recipients are required")
                result["signal"] = send_signal(message, [str(item) for item in recipients])
            if "signalwire" in channels:
                result["signalwire"] = send_signalwire(message)
            self._send(200, {"ok": True, "result": result})
        except Exception as exc:
            self._send(400, {"ok": False, "error": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        log(fmt % args)


def main() -> int:
    log(f"starting on {CONFIG.host}:{CONFIG.port}; Signal API {CONFIG.signal_api_base}; model {CONFIG.litellm_model}")
    threading.Thread(target=poll_loop, name="signal-poller", daemon=True).start()
    server = ThreadingHTTPServer((CONFIG.host, CONFIG.port), Handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
