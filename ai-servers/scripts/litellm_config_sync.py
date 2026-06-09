#!/usr/bin/env python3
"""Synchronize LiteLLM DB/Admin UI models with litellm-proxy/config.yaml."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml

try:
    import nacl.secret
except ImportError:  # pragma: no cover - installed with LiteLLM in this venv
    nacl = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "litellm-proxy" / "config.yaml"
DEFAULT_STATE_PATH = ROOT / "litellm-proxy" / ".config-sync-state.json"
DEFAULT_UI_CONFIG_PATH = ROOT / "litellm-proxy" / "ui-db.yaml"
DEFAULT_UI_STATE_PATH = ROOT / "litellm-proxy" / ".ui-db-sync-state.json"
DEFAULT_BACKUP_DIR = ROOT / "litellm-proxy" / "backups"
DEFAULT_BASE_URL = "http://127.0.0.1:8092"
DEFAULT_DATABASE_URL = "postgresql://michaelahern@localhost:5432/litellm"
MODEL_ID_NAMESPACE = uuid.UUID("4fe1f77c-8122-4cf0-940d-2b1556f41c68")

SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "authorization",
    "credential",
)
NON_SECRET_KEY_PARTS = (
    "api_key_help_url",
    "allow_client_side_credentials",
    "credential_name",
    "litellm_credential_name",
    "send_user_api_key",
    "send_user_api_key_alias",
)
SAFE_SECRET_PREFIXES = ("os.environ/", "${", "$")
SAFE_SECRET_VALUES = {"", "dummy", "none", "null"}

UI_NEVER_SYNC_COLUMNS = {
    "credentials",
    "env",
    "extra_headers",
    "keys",
    "static_headers",
}

UI_TABLE_SPECS: dict[str, dict[str, Any]] = {
    "guardrails": {
        "table": "LiteLLM_GuardrailsTable",
        "pk": "guardrail_id",
        "columns": [
            ("guardrail_id", "text"),
            ("guardrail_name", "text"),
            ("litellm_params", "jsonb"),
            ("guardrail_info", "jsonb"),
            ("created_at", "timestamp"),
            ("updated_at", "timestamp"),
            ("team_id", "text"),
            ("reviewed_at", "timestamp"),
            ("status", "text"),
            ("submitted_at", "timestamp"),
        ],
    },
    "policies": {
        "table": "LiteLLM_PolicyTable",
        "pk": "policy_id",
        "columns": [
            ("policy_id", "text"),
            ("policy_name", "text"),
            ("inherit", "bool"),
            ("description", "text"),
            ("guardrails_add", "text[]"),
            ("guardrails_remove", "text[]"),
            ("condition", "jsonb"),
            ("created_at", "timestamp"),
            ("created_by", "text"),
            ("updated_at", "timestamp"),
            ("updated_by", "text"),
            ("pipeline", "jsonb"),
            ("is_latest", "bool"),
            ("parent_version_id", "text"),
            ("production_at", "timestamp"),
            ("published_at", "timestamp"),
            ("version_number", "int"),
            ("version_status", "text"),
        ],
    },
    "policy_attachments": {
        "table": "LiteLLM_PolicyAttachmentTable",
        "pk": "attachment_id",
        "columns": [
            ("attachment_id", "text"),
            ("policy_name", "text"),
            ("scope", "text"),
            ("teams", "text[]"),
            ("models", "text[]"),
            ("created_at", "timestamp"),
            ("created_by", "text"),
            ("updated_at", "timestamp"),
            ("updated_by", "text"),
            ("tags", "text[]"),
        ],
    },
    "mcp_servers": {
        "table": "LiteLLM_MCPServerTable",
        "pk": "server_id",
        "columns": [
            ("server_id", "text"),
            ("server_name", "text"),
            ("description", "text"),
            ("url", "text"),
            ("transport", "text"),
            ("auth_type", "text"),
            ("created_at", "timestamp"),
            ("created_by", "text"),
            ("updated_at", "timestamp"),
            ("updated_by", "text"),
            ("status", "text"),
            ("last_health_check", "timestamp"),
            ("health_check_error", "text"),
            ("mcp_info", "jsonb"),
            ("args", "text[]"),
            ("command", "text"),
            ("mcp_access_groups", "text[]"),
            ("alias", "text"),
            ("allowed_tools", "text[]"),
            ("authorization_url", "text"),
            ("registration_url", "text"),
            ("token_url", "text"),
            ("allow_all_keys", "bool"),
            ("available_on_public_internet", "bool"),
            ("spec_path", "text"),
            ("byok_api_key_help_url", "text"),
            ("byok_description", "text[]"),
            ("is_byok", "bool"),
            ("tool_name_to_description", "jsonb"),
            ("tool_name_to_display_name", "jsonb"),
            ("approval_status", "text"),
            ("submitted_by", "text"),
            ("submitted_at", "timestamp"),
            ("reviewed_at", "timestamp"),
            ("review_notes", "text"),
            ("source_url", "text"),
            ("instructions", "text"),
        ],
    },
    "mcp_toolsets": {
        "table": "LiteLLM_MCPToolsetTable",
        "pk": "toolset_id",
        "columns": [
            ("toolset_id", "text"),
            ("toolset_name", "text"),
            ("description", "text"),
            ("tools", "jsonb"),
            ("created_at", "timestamp"),
            ("created_by", "text"),
            ("updated_at", "timestamp"),
            ("updated_by", "text"),
        ],
    },
    "managed_vector_store_resources": {
        "table": "LiteLLM_ManagedVectorStoreTable",
        "pk": "id",
        "columns": [
            ("id", "text"),
            ("unified_resource_id", "text"),
            ("resource_object", "jsonb"),
            ("model_mappings", "jsonb"),
            ("flat_model_resource_ids", "text[]"),
            ("storage_backend", "text"),
            ("storage_url", "text"),
            ("created_at", "timestamp"),
            ("created_by", "text"),
            ("updated_at", "timestamp"),
            ("updated_by", "text"),
        ],
    },
    "managed_vector_stores": {
        "table": "LiteLLM_ManagedVectorStoresTable",
        "pk": "vector_store_id",
        "columns": [
            ("vector_store_id", "text"),
            ("custom_llm_provider", "text"),
            ("vector_store_name", "text"),
            ("vector_store_description", "text"),
            ("vector_store_metadata", "jsonb"),
            ("created_at", "timestamp"),
            ("updated_at", "timestamp"),
            ("litellm_credential_name", "text"),
            ("litellm_params", "jsonb"),
            ("team_id", "text"),
            ("user_id", "text"),
        ],
    },
    "managed_vector_store_indexes": {
        "table": "LiteLLM_ManagedVectorStoreIndexTable",
        "pk": "id",
        "columns": [
            ("id", "text"),
            ("index_name", "text"),
            ("litellm_params", "jsonb"),
            ("index_info", "jsonb"),
            ("created_at", "timestamp"),
            ("created_by", "text"),
            ("updated_at", "timestamp"),
            ("updated_by", "text"),
        ],
    },
    "budgets": {
        "table": "LiteLLM_BudgetTable",
        "pk": "budget_id",
        "columns": [
            ("budget_id", "text"),
            ("max_budget", "numeric"),
            ("soft_budget", "numeric"),
            ("max_parallel_requests", "int"),
            ("tpm_limit", "bigint"),
            ("rpm_limit", "bigint"),
            ("model_max_budget", "jsonb"),
            ("budget_duration", "text"),
            ("budget_reset_at", "timestamp"),
            ("created_at", "timestamp"),
            ("created_by", "text"),
            ("updated_at", "timestamp"),
            ("updated_by", "text"),
            ("allowed_models", "text[]"),
        ],
    },
    "teams": {
        "table": "LiteLLM_TeamTable",
        "pk": "team_id",
        "columns": [
            ("team_id", "text"),
            ("team_alias", "text"),
            ("organization_id", "text"),
            ("admins", "text[]"),
            ("members", "text[]"),
            ("members_with_roles", "jsonb"),
            ("metadata", "jsonb"),
            ("max_budget", "numeric"),
            ("spend", "numeric"),
            ("models", "text[]"),
            ("max_parallel_requests", "int"),
            ("tpm_limit", "bigint"),
            ("rpm_limit", "bigint"),
            ("budget_duration", "text"),
            ("budget_reset_at", "timestamp"),
            ("blocked", "bool"),
            ("created_at", "timestamp"),
            ("updated_at", "timestamp"),
            ("model_spend", "jsonb"),
            ("model_max_budget", "jsonb"),
            ("model_id", "int"),
            ("team_member_permissions", "text[]"),
            ("object_permission_id", "text"),
            ("router_settings", "jsonb"),
            ("policies", "text[]"),
            ("allow_team_guardrail_config", "bool"),
            ("soft_budget", "numeric"),
            ("access_group_ids", "text[]"),
            ("budget_limits", "jsonb"),
            ("default_team_member_models", "text[]"),
        ],
    },
    "memory": {
        "table": "LiteLLM_MemoryTable",
        "pk": "memory_id",
        "columns": [
            ("memory_id", "text"),
            ("key", "text"),
            ("value", "text"),
            ("metadata", "jsonb"),
            ("user_id", "text"),
            ("team_id", "text"),
            ("created_at", "timestamp"),
            ("created_by", "text"),
            ("updated_at", "timestamp"),
            ("updated_by", "text"),
        ],
    },
    "cache_config": {
        "table": "LiteLLM_CacheConfig",
        "pk": "id",
        "columns": [
            ("id", "text"),
            ("cache_settings", "jsonb"),
            ("created_at", "timestamp"),
            ("updated_at", "timestamp"),
        ],
    },
    "agents": {
        "table": "LiteLLM_AgentsTable",
        "pk": "agent_id",
        "columns": [
            ("agent_id", "text"),
            ("agent_name", "text"),
            ("litellm_params", "jsonb"),
            ("agent_card_params", "jsonb"),
            ("created_at", "timestamp"),
            ("created_by", "text"),
            ("updated_at", "timestamp"),
            ("updated_by", "text"),
            ("agent_access_groups", "text[]"),
            ("object_permission_id", "text"),
            ("tpm_limit", "int"),
            ("rpm_limit", "int"),
            ("session_tpm_limit", "int"),
            ("session_rpm_limit", "int"),
        ],
    },
    "skills": {
        "table": "LiteLLM_SkillsTable",
        "pk": "skill_id",
        "columns": [
            ("skill_id", "text"),
            ("display_title", "text"),
            ("description", "text"),
            ("instructions", "text"),
            ("source", "text"),
            ("latest_version", "text"),
            ("file_content", "bytea"),
            ("file_name", "text"),
            ("file_type", "text"),
            ("metadata", "jsonb"),
            ("created_at", "timestamp"),
            ("created_by", "text"),
            ("updated_at", "timestamp"),
            ("updated_by", "text"),
        ],
    },
    "config": {
        "table": "LiteLLM_Config",
        "pk": "param_name",
        "columns": [
            ("param_name", "text"),
            ("param_value", "jsonb"),
        ],
    },
}


class SyncError(RuntimeError):
    """Raised for expected sync failures with actionable messages."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def print_status(message: str) -> None:
    print(f"[litellm-config-sync] {message}", flush=True)


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_command(command: list[str], *, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SyncError(f"command failed: {' '.join(command)}\n{detail}")
    return result.stdout


def keychain_secret(service_name: str) -> str | None:
    user = os.environ.get("USER", "")
    if not user:
        return None
    try:
        value = run_command(
            [
                "security",
                "find-generic-password",
                "-a",
                user,
                "-s",
                service_name,
                "-w",
            ]
        ).strip()
    except SyncError:
        return None
    return value or None


def ensure_runtime_env(*, need_master_key: bool, need_salt_key: bool) -> None:
    os.environ.setdefault("DATABASE_URL", DEFAULT_DATABASE_URL)

    if need_master_key and not os.environ.get("LITELLM_MASTER_KEY"):
        master_key = keychain_secret("litellm-master-key")
        if not master_key:
            raise SyncError("LITELLM_MASTER_KEY missing and litellm-master-key not found in Keychain")
        os.environ["LITELLM_MASTER_KEY"] = master_key

    if need_salt_key and not os.environ.get("LITELLM_SALT_KEY"):
        salt_key = keychain_secret("litellm-salt-key")
        if not salt_key:
            raise SyncError("LITELLM_SALT_KEY missing and litellm-salt-key not found in Keychain")
        os.environ["LITELLM_SALT_KEY"] = salt_key


def database_name() -> str:
    raw_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    parsed = urlparse(raw_url)
    if parsed.path and parsed.path != "/":
        return parsed.path.lstrip("/")
    return "litellm"


def psql_json(query: str) -> Any:
    ensure_runtime_env(need_master_key=False, need_salt_key=False)
    output = run_command(["psql", "-d", database_name(), "-v", "ON_ERROR_STOP=1", "-Atc", query])
    text = output.strip()
    return json.loads(text or "[]")


def run_psql_script(sql: str) -> str:
    ensure_runtime_env(need_master_key=False, need_salt_key=False)
    result = subprocess.run(
        ["psql", "-d", database_name(), "-v", "ON_ERROR_STOP=1"],
        input=sql,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SyncError(f"psql script failed\n{detail}")
    return result.stdout


def load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SyncError(f"config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise SyncError(f"config file must contain a YAML mapping: {path}")
    return data


def write_yaml_config(path: Path, data: dict[str, Any], *, dry_run: bool) -> None:
    rendered = yaml.safe_dump(data, sort_keys=False, allow_unicode=False, width=120)
    if dry_run:
        print_status(f"dry-run: would write {path}")
        return

    DEFAULT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = DEFAULT_BACKUP_DIR / f"{path.name}.{stamp}.bak"
        shutil.copy2(path, backup_path)
        print_status(f"backup written: {backup_path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(rendered)
    os.replace(tmp_name, path)
    print_status(f"wrote {path}")


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_state(path: Path, config_hash: str, db_signature: str, *, dry_run: bool) -> None:
    state = {
        "config_hash": config_hash,
        "db_signature": db_signature,
        "updated_at": now_iso(),
    }
    if dry_run:
        print_status(f"dry-run: would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(state, handle, sort_keys=True, indent=2)
        handle.write("\n")
    os.replace(tmp_name, path)


def model_list(config: dict[str, Any]) -> list[dict[str, Any]]:
    models = config.get("model_list")
    if models is None:
        config["model_list"] = []
        return config["model_list"]
    if not isinstance(models, list):
        raise SyncError("config model_list must be a list")
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            raise SyncError(f"model_list[{index}] must be a mapping")
    return models


def normalize_json_object(value: Any, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if value is None:
        return {} if fallback is None else fallback
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise SyncError(f"expected JSON object, got {type(value).__name__}")


def model_identity(model: dict[str, Any], index: int) -> str:
    model_name = str(model.get("model_name", ""))
    params = normalize_json_object(model.get("litellm_params"), {})
    litellm_model = str(params.get("model", ""))
    api_base = str(params.get("api_base", ""))
    return f"{model_name}|{litellm_model}|{api_base}|{index}"


def ensure_model_ids(config: dict[str, Any]) -> tuple[int, list[str]]:
    changed = 0
    ids: list[str] = []
    used: set[str] = set()
    for index, model in enumerate(model_list(config)):
        info = normalize_json_object(model.get("model_info"), {})
        model["model_info"] = info

        model_id = info.get("id")
        if not model_id:
            base = model_identity(model, index)
            model_id = str(uuid.uuid5(MODEL_ID_NAMESPACE, base))
            suffix = 1
            while model_id in used:
                model_id = str(uuid.uuid5(MODEL_ID_NAMESPACE, f"{base}|{suffix}"))
                suffix += 1
            info["id"] = model_id
            changed += 1

        model_id = str(model_id)
        if model_id in used:
            raise SyncError(f"duplicate model_info.id found: {model_id}")
        used.add(model_id)
        ids.append(model_id)
    return changed, ids


def validate_model_payloads(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for index, model in enumerate(model_list(config)):
        model_name = model.get("model_name")
        params = model.get("litellm_params")
        if not model_name:
            errors.append(f"model_list[{index}] missing model_name")
        if not isinstance(params, dict):
            errors.append(f"model_list[{index}] missing litellm_params")
        elif not params.get("model"):
            errors.append(f"model_list[{index}] missing litellm_params.model")
    return errors


def db_models() -> list[dict[str, Any]]:
    rows = psql_json(
        """
        select coalesce(
          jsonb_agg(
            jsonb_build_object(
              'model_id', model_id,
              'model_name', model_name,
              'litellm_params', litellm_params,
              'model_info', model_info,
              'updated_at', to_char(updated_at, 'YYYY-MM-DD"T"HH24:MI:SS.US')
            )
            order by model_id
          )::text,
          '[]'
        )
        from "LiteLLM_ProxyModelTable";
        """
    )
    if not isinstance(rows, list):
        raise SyncError("unexpected DB model query result")
    return rows


def db_signature(rows: list[dict[str, Any]] | None = None) -> str:
    rows = db_models() if rows is None else rows
    return sha256_text(stable_json(rows))


def db_models_by_id(rows: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    rows = db_models() if rows is None else rows
    return {str(row["model_id"]): row for row in rows if row.get("model_id")}


def decrypt_string(value: str, key_path: str) -> Any:
    salt_key = os.environ.get("LITELLM_SALT_KEY")
    if not salt_key:
        return value
    if nacl is None:
        return value
    try:
        try:
            decoded = base64.urlsafe_b64decode(value)
        except Exception:
            decoded = base64.b64decode(value)
        signing_key = hashlib.sha256(salt_key.encode("utf-8")).digest()
        box = nacl.secret.SecretBox(signing_key)
        return box.decrypt(decoded).decode("utf-8")
    except Exception:
        return value


def decrypt_tree(value: Any, key_path: str = "") -> Any:
    if isinstance(value, dict):
        return {key: decrypt_tree(item, f"{key_path}.{key}" if key_path else str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [decrypt_tree(item, key_path) for item in value]
    if isinstance(value, str):
        return decrypt_string(value, key_path)
    return value


def is_secret_key(key_path: str) -> bool:
    lowered = key_path.lower()
    if any(part in lowered for part in NON_SECRET_KEY_PARTS):
        return False
    return any(part in lowered for part in SECRET_KEY_PARTS)


def is_safe_secret_value(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if stripped.lower() in SAFE_SECRET_VALUES:
        return True
    return stripped.startswith(SAFE_SECRET_PREFIXES)


def get_nested(mapping: dict[str, Any], path: list[str]) -> Any:
    current: Any = mapping
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def sanitize_secrets(value: Any, previous: Any, path: list[str] | None = None) -> Any:
    path = [] if path is None else path
    if isinstance(value, dict):
        previous_map = previous if isinstance(previous, dict) else {}
        return {
            key: sanitize_secrets(item, previous_map.get(key), [*path, str(key)])
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_secrets(item, None, path) for item in value]

    key_path = ".".join(path)
    if is_secret_key(key_path) and not is_safe_secret_value(value):
        if is_safe_secret_value(previous):
            return previous
        raise SyncError(
            f"refusing to write raw secret from DB to YAML at litellm_params.{key_path}; "
            "replace it in the Admin UI with an os.environ/... reference or keep a safe YAML value"
        )
    return value


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_literal(value: Any, type_name: str) -> str:
    if value is None:
        return "NULL"
    if type_name == "jsonb":
        return f"{sql_string(stable_json(value))}::jsonb"
    if type_name == "text[]":
        if not isinstance(value, list):
            raise SyncError(f"expected list for text[] value, got {type(value).__name__}")
        if not value:
            return "ARRAY[]::text[]"
        return "ARRAY[" + ", ".join(sql_string(str(item)) for item in value) + "]::text[]"
    if type_name == "bool":
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return "TRUE" if value.lower() == "true" else "FALSE"
        raise SyncError(f"expected bool value, got {value!r}")
    if type_name in {"int", "bigint"}:
        return str(int(value))
    if type_name == "numeric":
        return str(float(value))
    if type_name == "bytea":
        if not isinstance(value, str):
            raise SyncError(f"expected base64 string for bytea value, got {type(value).__name__}")
        try:
            base64.b64decode(value, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise SyncError("expected valid base64 string for bytea value") from exc
        return f"decode({sql_string(value)}, 'base64')"
    if type_name == "timestamp":
        return f"{sql_string(str(value))}::timestamp"
    return sql_string(str(value))


def ui_file_hash(path: Path) -> str:
    return file_hash(path) if path.exists() else "absent"


def ui_empty_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {"ui_db_version": 1}
    for section in UI_TABLE_SPECS:
        payload[section] = []
    return payload


def sanitize_ui_value(value: Any, path: list[str]) -> Any:
    if isinstance(value, dict):
        return {key: sanitize_ui_value(item, [*path, str(key)]) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_ui_value(item, path) for item in value]

    key_path = ".".join(path)
    if is_secret_key(key_path) and not is_safe_secret_value(value):
        raise SyncError(
            f"refusing to sync raw secret at {key_path}; use an os.environ/... reference "
            "or keep that value out of ui-db.yaml"
        )
    return value


def sanitize_ui_row(row: dict[str, Any], section: str) -> dict[str, Any]:
    if section == "config":
        param_name = str(row.get("param_name", ""))
        param_value = row.get("param_value")
        if is_secret_key(param_name) and not is_safe_secret_value(param_value):
            raise SyncError(f"refusing to sync raw LiteLLM_Config secret: {param_name}")
    return {key: sanitize_ui_value(value, [section, str(key)]) for key, value in row.items()}


def ui_spec_columns(spec: dict[str, Any]) -> dict[str, str]:
    return {str(name): str(type_name) for name, type_name in spec["columns"]}


def ui_select_expression(column: str, type_name: str) -> str:
    if type_name == "bytea":
        return f"encode({quote_ident(column)}, 'base64')"
    return quote_ident(column)


def db_ui_rows(section: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    columns = ui_spec_columns(spec)
    parts = ",\n              ".join(
        f"{sql_string(column)}, {ui_select_expression(column, type_name)}"
        for column, type_name in columns.items()
    )
    pk = str(spec["pk"])
    table = quote_ident(str(spec["table"]))
    rows = psql_json(
        f"""
        select coalesce(
          jsonb_agg(
            jsonb_build_object(
              {parts}
            )
            order by {quote_ident(pk)}
          )::text,
          '[]'
        )
        from {table};
        """
    )
    if not isinstance(rows, list):
        raise SyncError(f"unexpected DB result for {section}")
    return [sanitize_ui_row(dict(row), section) for row in rows]


def db_ui_payload() -> dict[str, Any]:
    payload = ui_empty_payload()
    for section, spec in UI_TABLE_SPECS.items():
        payload[section] = db_ui_rows(section, spec)
    return payload


def ui_payload_signature(payload: dict[str, Any]) -> str:
    comparable = {section: payload.get(section, []) for section in UI_TABLE_SPECS}
    return sha256_text(stable_json(comparable))


def ui_db_signature(payload: dict[str, Any] | None = None) -> str:
    payload = db_ui_payload() if payload is None else payload
    return ui_payload_signature(payload)


def ui_row_count(payload: dict[str, Any]) -> int:
    return sum(len(payload.get(section, [])) for section in UI_TABLE_SPECS)


def load_ui_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SyncError(f"UI DB config file not found: {path}")
    data = load_yaml_config(path)
    version = data.get("ui_db_version", 1)
    if version != 1:
        raise SyncError(f"unsupported ui_db_version: {version}")

    payload = ui_empty_payload()
    for section, spec in UI_TABLE_SPECS.items():
        rows = data.get(section, [])
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            raise SyncError(f"{path}: {section} must be a list")

        columns = ui_spec_columns(spec)
        pk = str(spec["pk"])
        normalized: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise SyncError(f"{path}: {section}[{index}] must be a mapping")
            disallowed = sorted(set(row) & UI_NEVER_SYNC_COLUMNS)
            if disallowed:
                raise SyncError(f"{path}: {section}[{index}] contains non-syncable column(s): {', '.join(disallowed)}")
            unknown = sorted(set(row) - set(columns))
            if unknown:
                raise SyncError(f"{path}: {section}[{index}] contains unknown column(s): {', '.join(unknown)}")
            if not row.get(pk):
                raise SyncError(f"{path}: {section}[{index}] missing primary key {pk}")
            normalized.append(sanitize_ui_row(dict(row), section))
        payload[section] = normalized
    return payload


def upsert_ui_rows(section: str, spec: dict[str, Any], rows: list[dict[str, Any]], *, dry_run: bool) -> int:
    if not rows:
        return 0

    columns = ui_spec_columns(spec)
    pk = str(spec["pk"])
    table = quote_ident(str(spec["table"]))
    statements = ["BEGIN;"]

    for row in rows:
        present_columns = [column for column in columns if column in row]
        if pk not in present_columns:
            raise SyncError(f"{section} row missing primary key {pk}")
        column_sql = ", ".join(quote_ident(column) for column in present_columns)
        value_sql = ", ".join(sql_literal(row[column], columns[column]) for column in present_columns)
        assignments = [
            f"{quote_ident(column)} = EXCLUDED.{quote_ident(column)}"
            for column in present_columns
            if column != pk
        ]
        conflict_sql = "DO UPDATE SET " + ", ".join(assignments) if assignments else "DO NOTHING"
        statements.append(
            f"INSERT INTO {table} ({column_sql}) VALUES ({value_sql}) "
            f"ON CONFLICT ({quote_ident(pk)}) {conflict_sql};"
        )

    statements.append("COMMIT;")
    if dry_run:
        print_status(f"dry-run: would upsert {len(rows)} row(s) into {section}")
    else:
        run_psql_script("\n".join(statements))
    return len(rows)


def import_ui_db(ui_config_path: Path, ui_state_path: Path, *, dry_run: bool) -> None:
    payload = load_ui_config(ui_config_path)
    total = 0
    for section, spec in UI_TABLE_SPECS.items():
        total += upsert_ui_rows(section, spec, payload.get(section, []), dry_run=dry_run)
    print_status(f"UI YAML -> DB complete: upserted={total}")
    write_state(ui_state_path, ui_file_hash(ui_config_path), ui_db_signature(), dry_run=dry_run)


def export_ui_db(ui_config_path: Path, ui_state_path: Path, *, dry_run: bool) -> None:
    payload = db_ui_payload()
    write_yaml_config(ui_config_path, payload, dry_run=dry_run)
    print_status(f"DB -> UI YAML complete: exported={ui_row_count(payload)} row(s)")
    write_state(ui_state_path, ui_file_hash(ui_config_path), ui_db_signature(payload), dry_run=dry_run)


def sync_ui_once(
    ui_config_path: Path,
    ui_state_path: Path,
    *,
    dry_run: bool,
    prefer: str | None,
) -> None:
    state = load_state(ui_state_path)
    current_config_hash = ui_file_hash(ui_config_path)
    current_db_signature = ui_db_signature()

    if not state:
        db_count = ui_row_count(db_ui_payload())
        if ui_config_path.exists() and db_count == 0:
            print_status("no UI state and UI DB empty; importing ui-db.yaml")
            import_ui_db(ui_config_path, ui_state_path, dry_run=dry_run)
        else:
            print_status("no UI state or UI DB populated; exporting UI DB")
            export_ui_db(ui_config_path, ui_state_path, dry_run=dry_run)
        return

    yaml_changed = state.get("config_hash") != current_config_hash
    db_changed = state.get("db_signature") != current_db_signature

    if yaml_changed and not ui_config_path.exists():
        print_status("ui-db.yaml absent; exporting UI DB instead of deleting DB state")
        export_ui_db(ui_config_path, ui_state_path, dry_run=dry_run)
    elif yaml_changed and db_changed:
        if prefer == "yaml":
            print_status("UI YAML and DB both changed; preferring UI YAML")
            import_ui_db(ui_config_path, ui_state_path, dry_run=dry_run)
        elif prefer == "db":
            print_status("UI YAML and DB both changed; preferring UI DB")
            export_ui_db(ui_config_path, ui_state_path, dry_run=dry_run)
        else:
            raise SyncError("UI YAML and DB both changed since last sync; rerun with --prefer yaml or --prefer db")
    elif yaml_changed:
        print_status("UI YAML changed; importing to DB")
        import_ui_db(ui_config_path, ui_state_path, dry_run=dry_run)
    elif db_changed:
        print_status("UI DB changed; exporting to ui-db.yaml")
        export_ui_db(ui_config_path, ui_state_path, dry_run=dry_run)
    else:
        print_status("UI YAML and DB already in sync")


def previous_yaml_by_id(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for model in model_list(config):
        info = normalize_json_object(model.get("model_info"), {})
        model_id = info.get("id")
        if model_id:
            result[str(model_id)] = model
    return result


def api_headers() -> dict[str, str]:
    ensure_runtime_env(need_master_key=True, need_salt_key=False)
    return {
        "Authorization": f"Bearer {os.environ['LITELLM_MASTER_KEY']}",
        "Content-Type": "application/json",
    }


def wait_for_proxy(base_url: str, timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/health/liveliness", timeout=3)
            if 200 <= response.status_code < 400:
                return
            last_error = f"HTTP {response.status_code}"
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(1)
    raise SyncError(f"LiteLLM proxy not ready at {base_url}: {last_error}")


def request_model_endpoint(
    method: str,
    base_url: str,
    path: str,
    payload: dict[str, Any],
    *,
    dry_run: bool,
) -> None:
    if dry_run:
        print_status(f"dry-run: would {method} {path} for {payload.get('model_name')}")
        return
    response = httpx.request(
        method,
        f"{base_url}{path}",
        headers=api_headers(),
        json=payload,
        timeout=60,
    )
    if response.status_code >= 400:
        raise SyncError(f"{method} {path} failed for {payload.get('model_name')}: {response.status_code} {response.text}")


def import_yaml_models(config_path: Path, state_path: Path, base_url: str, *, dry_run: bool) -> None:
    config = load_yaml_config(config_path)
    missing_ids, _ids = ensure_model_ids(config)
    errors = validate_model_payloads(config)
    if errors:
        raise SyncError("; ".join(errors))
    if missing_ids:
        print_status(f"added stable model_info.id to {missing_ids} YAML model(s)")
        write_yaml_config(config_path, config, dry_run=dry_run)

    wait_for_proxy(base_url)
    rows = db_models()
    existing = db_models_by_id(rows)
    created = 0
    updated = 0
    for model in model_list(config):
        info = normalize_json_object(model.get("model_info"), {})
        model_id = str(info["id"])
        payload = {
            "model_name": model["model_name"],
            "litellm_params": deepcopy(model["litellm_params"]),
            "model_info": deepcopy(info),
        }
        if model_id in existing:
            request_model_endpoint("POST", base_url, "/model/update", payload, dry_run=dry_run)
            updated += 1
        else:
            request_model_endpoint("POST", base_url, "/model/new", payload, dry_run=dry_run)
            created += 1
    print_status(f"YAML -> DB complete: created={created}, updated={updated}")
    write_state(state_path, file_hash(config_path), db_signature(), dry_run=dry_run)


def export_db_models(config_path: Path, state_path: Path, *, dry_run: bool) -> None:
    ensure_runtime_env(need_master_key=False, need_salt_key=True)
    config = load_yaml_config(config_path)
    ensure_model_ids(config)
    previous = previous_yaml_by_id(config)
    exported: list[dict[str, Any]] = []

    for row in db_models():
        model_id = str(row["model_id"])
        params = decrypt_tree(normalize_json_object(row.get("litellm_params"), {}), "litellm_params")
        info = normalize_json_object(row.get("model_info"), {})
        info["id"] = model_id
        old_params = normalize_json_object(previous.get(model_id, {}).get("litellm_params"), {})
        params = sanitize_secrets(params, old_params)
        exported.append(
            {
                "model_name": row["model_name"],
                "litellm_params": params,
                "model_info": info,
            }
        )

    config["model_list"] = exported
    general_settings = normalize_json_object(config.get("general_settings"), {})
    general_settings["store_model_in_db"] = True
    config["general_settings"] = general_settings

    write_yaml_config(config_path, config, dry_run=dry_run)
    print_status(f"DB -> YAML complete: exported={len(exported)}")
    write_state(state_path, file_hash(config_path), db_signature(), dry_run=dry_run)


def bootstrap(config_path: Path, state_path: Path, base_url: str, *, dry_run: bool, force_import: bool) -> None:
    config = load_yaml_config(config_path)
    missing_ids, _ids = ensure_model_ids(config)
    if missing_ids:
        print_status(f"added stable model_info.id to {missing_ids} YAML model(s)")
        write_yaml_config(config_path, config, dry_run=dry_run)

    count = len(db_models())
    if count == 0 or force_import:
        import_yaml_models(config_path, state_path, base_url, dry_run=dry_run)
    else:
        print_status(f"DB already contains {count} model(s); recording sync state")
        write_state(state_path, file_hash(config_path), db_signature(), dry_run=dry_run)


def sync_once(
    config_path: Path,
    state_path: Path,
    base_url: str,
    *,
    dry_run: bool,
    prefer: str | None,
) -> None:
    state = load_state(state_path)
    current_config_hash = file_hash(config_path)
    current_db_signature = db_signature()

    if not state:
        if len(db_models()) == 0:
            print_status("no state and DB empty; importing YAML")
            import_yaml_models(config_path, state_path, base_url, dry_run=dry_run)
        else:
            print_status("no state and DB populated; exporting DB")
            export_db_models(config_path, state_path, dry_run=dry_run)
        return

    yaml_changed = state.get("config_hash") != current_config_hash
    db_changed = state.get("db_signature") != current_db_signature

    if yaml_changed and db_changed:
        if prefer == "yaml":
            print_status("YAML and DB both changed; preferring YAML")
            import_yaml_models(config_path, state_path, base_url, dry_run=dry_run)
        elif prefer == "db":
            print_status("YAML and DB both changed; preferring DB")
            export_db_models(config_path, state_path, dry_run=dry_run)
        else:
            raise SyncError("YAML and DB both changed since last sync; rerun with --prefer yaml or --prefer db")
    elif yaml_changed:
        print_status("YAML changed; importing to DB")
        import_yaml_models(config_path, state_path, base_url, dry_run=dry_run)
    elif db_changed:
        print_status("DB changed; exporting to YAML")
        export_db_models(config_path, state_path, dry_run=dry_run)
    else:
        print_status("YAML and DB already in sync")


def check(config_path: Path, state_path: Path) -> int:
    config = load_yaml_config(config_path)
    missing_ids = 0
    duplicate_ids: set[str] = set()
    seen: set[str] = set()
    for model in model_list(config):
        info = normalize_json_object(model.get("model_info"), {})
        model_id = info.get("id")
        if not model_id:
            missing_ids += 1
        elif str(model_id) in seen:
            duplicate_ids.add(str(model_id))
        else:
            seen.add(str(model_id))

    errors = validate_model_payloads(config)
    general_settings = normalize_json_object(config.get("general_settings"), {})
    store_model_in_db = general_settings.get("store_model_in_db") is True
    rows = db_models()
    state = load_state(state_path)
    print_status(f"config={config_path}")
    print_status(f"yaml_models={len(model_list(config))} missing_ids={missing_ids} duplicate_ids={len(duplicate_ids)}")
    print_status(f"db_models={len(rows)} state={'present' if state else 'absent'} store_model_in_db={store_model_in_db}")

    if errors:
        for error in errors:
            print_status(f"ERROR {error}")
    if duplicate_ids:
        for model_id in sorted(duplicate_ids):
            print_status(f"ERROR duplicate model_info.id: {model_id}")
    if not store_model_in_db:
        print_status("ERROR general_settings.store_model_in_db must be true")

    return 1 if errors or duplicate_ids or not store_model_in_db else 0


def check_ui_db(ui_config_path: Path, ui_state_path: Path) -> int:
    db_payload = db_ui_payload()
    db_sig = ui_payload_signature(db_payload)
    state = load_state(ui_state_path)
    if ui_config_path.exists():
        yaml_payload = load_ui_config(ui_config_path)
        yaml_sig = ui_payload_signature(yaml_payload)
        yaml_count = ui_row_count(yaml_payload)
    else:
        yaml_payload = ui_empty_payload()
        yaml_sig = "absent"
        yaml_count = 0

    print_status(f"ui_config={ui_config_path}")
    print_status(f"ui_yaml_rows={yaml_count} db_ui_rows={ui_row_count(db_payload)} state={'present' if state else 'absent'}")
    for section in UI_TABLE_SPECS:
        yaml_section_count = len(yaml_payload.get(section, []))
        db_section_count = len(db_payload.get(section, []))
        print_status(f"{section}: yaml={yaml_section_count} db={db_section_count}")
    in_sync = yaml_sig == db_sig
    print_status(f"ui_in_sync={in_sync}")
    return 0 if in_sync else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--ui-config", type=Path, default=DEFAULT_UI_CONFIG_PATH)
    parser.add_argument("--ui-state", type=Path, default=DEFAULT_UI_STATE_PATH)
    parser.add_argument("--base-url", default=os.environ.get("LITELLM_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--dry-run", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check", help="validate YAML and report DB/state status")
    subparsers.add_parser("check-ui-db", help="validate UI DB YAML and report DB/state status")

    bootstrap_parser = subparsers.add_parser("bootstrap", help="add stable IDs and import YAML if DB is empty")
    bootstrap_parser.add_argument("--force-import", action="store_true", help="import YAML even if DB already has models")

    subparsers.add_parser("import-yaml", help="upsert YAML models into LiteLLM DB")
    subparsers.add_parser("export-db", help="export LiteLLM DB models back to YAML")
    subparsers.add_parser("import-ui-db", help="upsert ui-db.yaml into LiteLLM UI DB tables")
    subparsers.add_parser("export-ui-db", help="export LiteLLM UI DB tables into ui-db.yaml")

    sync_parser = subparsers.add_parser("sync", help="sync the changed side since the last state")
    sync_parser.add_argument("--prefer", choices=["yaml", "db"], help="resolve simultaneous YAML/DB changes")

    sync_ui_parser = subparsers.add_parser("sync-ui-db", help="sync changed UI DB side since the last state")
    sync_ui_parser.add_argument("--prefer", choices=["yaml", "db"], help="resolve simultaneous YAML/DB changes")

    watch_parser = subparsers.add_parser("watch", help="continuously sync YAML and DB")
    watch_parser.add_argument("--interval", type=int, default=10)
    watch_parser.add_argument("--prefer", choices=["yaml", "db"], help="resolve simultaneous YAML/DB changes")

    watch_all_parser = subparsers.add_parser("watch-all", help="continuously sync models and UI DB tables")
    watch_all_parser.add_argument("--interval", type=int, default=10)
    watch_all_parser.add_argument("--prefer", choices=["yaml", "db"], help="resolve simultaneous YAML/DB changes")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            return check(args.config, args.state)
        if args.command == "check-ui-db":
            return check_ui_db(args.ui_config, args.ui_state)
        if args.command == "bootstrap":
            bootstrap(args.config, args.state, args.base_url, dry_run=args.dry_run, force_import=args.force_import)
            return 0
        if args.command == "import-yaml":
            import_yaml_models(args.config, args.state, args.base_url, dry_run=args.dry_run)
            return 0
        if args.command == "export-db":
            export_db_models(args.config, args.state, dry_run=args.dry_run)
            return 0
        if args.command == "import-ui-db":
            import_ui_db(args.ui_config, args.ui_state, dry_run=args.dry_run)
            return 0
        if args.command == "export-ui-db":
            export_ui_db(args.ui_config, args.ui_state, dry_run=args.dry_run)
            return 0
        if args.command == "sync":
            sync_once(args.config, args.state, args.base_url, dry_run=args.dry_run, prefer=args.prefer)
            return 0
        if args.command == "sync-ui-db":
            sync_ui_once(args.ui_config, args.ui_state, dry_run=args.dry_run, prefer=args.prefer)
            return 0
        if args.command == "watch":
            print_status(f"watching every {args.interval}s")
            while True:
                try:
                    sync_once(args.config, args.state, args.base_url, dry_run=args.dry_run, prefer=args.prefer)
                except Exception as exc:  # noqa: BLE001
                    print_status(f"ERROR {exc}")
                time.sleep(args.interval)
        if args.command == "watch-all":
            print_status(f"watching models and UI DB every {args.interval}s")
            while True:
                try:
                    sync_once(args.config, args.state, args.base_url, dry_run=args.dry_run, prefer=args.prefer)
                except Exception as exc:  # noqa: BLE001
                    print_status(f"ERROR model sync: {exc}")
                try:
                    sync_ui_once(args.ui_config, args.ui_state, dry_run=args.dry_run, prefer=args.prefer)
                except Exception as exc:  # noqa: BLE001
                    print_status(f"ERROR UI DB sync: {exc}")
                time.sleep(args.interval)
    except SyncError as exc:
        print_status(f"ERROR {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
