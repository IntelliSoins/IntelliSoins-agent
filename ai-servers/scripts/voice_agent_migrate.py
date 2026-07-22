#!/usr/bin/env python3
"""Apply idempotent PostgreSQL migrations for the Pipecat voice agent."""

from __future__ import annotations

from pathlib import Path

import psycopg

from voice_agent.config import load_config


def main() -> None:
    config = load_config()
    if not config.db_enabled or not config.db_dsn:
        raise RuntimeError(
            "VOICE_DB_DSN is required; production voice persistence cannot be disabled"
        )

    migration_dir = (
        Path(__file__).resolve().parent
        / "voice_agent"
        / "migrations"
    )
    migrations = sorted(migration_dir.glob("*.sql"))
    if not migrations:
        raise RuntimeError(f"no migrations found in {migration_dir}")
    with psycopg.connect(config.db_dsn) as conn:
        for migration in migrations:
            conn.execute(migration.read_text(encoding="utf-8"))
            print(f"Applied voice-agent migration: {migration.name}")


if __name__ == "__main__":
    main()
