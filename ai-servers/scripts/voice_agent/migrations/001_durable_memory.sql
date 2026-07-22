-- Derived durable memory for voice_agent (NOT the event log).
-- Exact event log (public.sessions / turns / tool_calls / tts_segments) remains
-- the source of truth for per-call traces. This table stores only *confirmed*
-- facts promoted from that log (consent, notes, follow-ups, triage intake,
-- opt-out, etc.), keyed by contact identity so memory survives across calls.
-- Explicit SQL repository — not an external memory SaaS product.
--
-- subject_id: required contact identity (trusted runtime, never LLM args).
-- source_session_id: audit trail of the call session that confirmed the fact.

CREATE TABLE IF NOT EXISTS public.durable_facts (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_id         text NOT NULL,
    source_session_id  text,
    fact_key           text NOT NULL,
    fact_value         jsonb NOT NULL DEFAULT '{}'::jsonb,
    category           text NOT NULL DEFAULT 'general',
    source_turn_pk     bigint REFERENCES public.turns(id) ON DELETE SET NULL,
    source_tool        text,
    idempotency_key    text,
    confirmed_at       timestamptz NOT NULL DEFAULT now(),
    superseded_at      timestamptz,
    meta               jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- Active facts are unique per contact (subject), not per call session.
CREATE UNIQUE INDEX IF NOT EXISTS durable_facts_active_key_uidx
    ON public.durable_facts (subject_id, fact_key)
    WHERE superseded_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS durable_facts_idempotency_uidx
    ON public.durable_facts (subject_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS durable_facts_subject_idx
    ON public.durable_facts (subject_id);

CREATE INDEX IF NOT EXISTS durable_facts_source_session_idx
    ON public.durable_facts (source_session_id);

CREATE INDEX IF NOT EXISTS durable_facts_category_idx
    ON public.durable_facts (category);

COMMENT ON TABLE public.durable_facts IS
    'Derived durable memory by subject_id; exact event log is separate SoT.';
