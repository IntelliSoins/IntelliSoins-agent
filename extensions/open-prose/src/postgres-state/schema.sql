-- OpenProse PostgreSQL state schema (canonical, idempotent).
CREATE SCHEMA IF NOT EXISTS openprose;

CREATE TABLE IF NOT EXISTS openprose.run (
    id TEXT PRIMARY KEY,
    program_path TEXT,
    program_source TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed', 'interrupted')),
    state_mode TEXT NOT NULL DEFAULT 'postgres',
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS openprose.execution (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES openprose.run(id) ON DELETE CASCADE,
    statement_index INTEGER NOT NULL,
    statement_text TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'executing', 'completed', 'failed', 'skipped')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    parent_id INTEGER REFERENCES openprose.execution(id) ON DELETE CASCADE,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS openprose.bindings (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES openprose.run(id) ON DELETE CASCADE,
    execution_id INTEGER,
    kind TEXT NOT NULL CHECK (kind IN ('input', 'output', 'let', 'const')),
    value TEXT,
    source_statement TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attachment_path TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_bindings_scope
    ON openprose.bindings (name, run_id, COALESCE(execution_id, -1));

CREATE TABLE IF NOT EXISTS openprose.agents (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    run_id TEXT,
    scope TEXT NOT NULL CHECK (scope IN ('execution', 'project', 'user', 'custom')),
    memory TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_scope
    ON openprose.agents (name, COALESCE(run_id, '__project__'));

CREATE TABLE IF NOT EXISTS openprose.agent_segments (
    id SERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL,
    run_id TEXT,
    segment_number INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    prompt TEXT,
    summary TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_segments_scope
    ON openprose.agent_segments (agent_name, COALESCE(run_id, '__project__'), segment_number);

CREATE TABLE IF NOT EXISTS openprose.imports (
    alias TEXT NOT NULL,
    run_id TEXT NOT NULL REFERENCES openprose.run(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    fetched_at TIMESTAMPTZ,
    inputs_schema JSONB,
    outputs_schema JSONB,
    content_hash TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    PRIMARY KEY (alias, run_id)
);

CREATE INDEX IF NOT EXISTS idx_execution_run_id ON openprose.execution(run_id);
CREATE INDEX IF NOT EXISTS idx_execution_status ON openprose.execution(status);
CREATE INDEX IF NOT EXISTS idx_execution_parent_id ON openprose.execution(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_execution_metadata_gin ON openprose.execution USING GIN (metadata jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_bindings_run_id ON openprose.bindings(run_id);
CREATE INDEX IF NOT EXISTS idx_bindings_execution_id ON openprose.bindings(execution_id) WHERE execution_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agents_run_id ON openprose.agents(run_id) WHERE run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_agents_project_scoped ON openprose.agents(name) WHERE run_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_agent_segments_lookup ON openprose.agent_segments(agent_name, run_id);
