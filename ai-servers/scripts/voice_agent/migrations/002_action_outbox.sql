-- Reliable handoff queue for actions that require a non-LLM consumer.
-- Examples: urgent human review, callback scheduling, opt-out propagation.

CREATE TABLE IF NOT EXISTS public.action_outbox (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type       text NOT NULL,
    subject_id       text NOT NULL,
    session_id       text NOT NULL,
    turn_pk          bigint REFERENCES public.turns(id) ON DELETE SET NULL,
    idempotency_key  text NOT NULL,
    payload          jsonb NOT NULL DEFAULT '{}'::jsonb,
    status           text NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    attempt_count    integer NOT NULL DEFAULT 0,
    available_at     timestamptz NOT NULL DEFAULT now(),
    created_at       timestamptz NOT NULL DEFAULT now(),
    processed_at     timestamptz,
    last_error       text,
    UNIQUE (subject_id, event_type, idempotency_key)
);

CREATE INDEX IF NOT EXISTS action_outbox_pending_idx
    ON public.action_outbox (available_at, id)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS action_outbox_session_idx
    ON public.action_outbox (session_id);

COMMENT ON TABLE public.action_outbox IS
    'Transactional handoff queue; consumers perform callbacks, opt-outs, and human escalation.';
