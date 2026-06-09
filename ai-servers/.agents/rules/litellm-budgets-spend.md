---
paths:
  - "**/sync-litellm-spend*"
  - "**/litellm*budget*"
  - "**/litellm*spend*"
  - "**/rate_limit*litellm*"
---

# LiteLLM Budgets & Spend Tracking

Cost control across 5 scopes: global, team, user, key, model, customer, agent. Rate limits enforced in-process (single instance) or via Redis (multi-instance sync).

## Budget hierarchy

Precedence (most specific wins):

1. **Model budget on key** (`model_max_budget`) — per-model cap
2. **Key budget** (`max_budget`) — total
3. **Team budget** (used when key has `team_id`)
4. **User budget** (used when no team)
5. **Global end-user budget** (`max_end_user_budget` in config)

## Global budget

```yaml
general_settings:
  master_key: sk-1234
litellm_settings:
  max_budget: 1000 # USD cap across all calls
  budget_duration: 30d # auto-reset window
  max_end_user_budget: 5 # cap per 'user' field in /chat/completions
```

## Virtual key budget

```bash
curl 'http://0.0.0.0:4000/key/generate' \
  -H 'Authorization: Bearer $MASTER' \
  -d '{
    "max_budget": 10,
    "budget_duration": "30d"
  }'
```

## Model-specific key budget

Per-model caps on a single key:

```bash
curl 'http://0.0.0.0:4000/key/generate' \
  -H 'Authorization: Bearer $MASTER' \
  -d '{
    "model_max_budget": {
      "gpt-4o": {"budget_limit": "0.50", "time_period": "1d"},
      "claude-sonnet": {"budget_limit": "2.00", "time_period": "1d"}
    }
  }'
```

Exceeded response:

```json
{
  "error": {
    "message": "LiteLLM Virtual Key exceeded budget for model=gpt-4o",
    "type": "budget_exceeded",
    "code": "400"
  }
}
```

## Team budget

```bash
curl 'http://localhost:4000/team/new' \
  -H 'Authorization: Bearer $MASTER' \
  -d '{
    "team_alias": "pubmed-agents",
    "members_with_roles": [{"role": "admin", "user_id": "uid"}],
    "max_budget": 500,
    "budget_duration": "30d",
    "rpm_limit": 1000,
    "tpm_limit": 100000
  }'
```

Team member individual cap within team:

```bash
# Step 1: user exists
curl 'http://0.0.0.0:4000/user/new' -d '{"user_id": "ishaan"}'

# Step 2: add with in-team budget
curl 'http://0.0.0.0:4000/team/member_add' \
  -d '{
    "team_id": "team-123",
    "max_budget_in_team": 50,
    "member": {"role": "user", "user_id": "ishaan"}
  }'
```

## User budget

Applies to all keys of that user:

```bash
curl 'http://localhost:4000/user/new' \
  -d '{
    "user_id": "krrish@berri.ai",
    "max_budget": 20,
    "budget_duration": "1mo"
  }'
```

Default for all `internal_user` role:

```yaml
litellm_settings:
  max_internal_user_budget: 20
  internal_user_budget_duration: "1mo"
```

## Customer / end-user budget

Map end-users (the `user` field in `/chat/completions` body) to budgets.

```bash
# Create reusable budget template
curl 'http://0.0.0.0:4000/budget/new' \
  -H 'Authorization: Bearer $MASTER' \
  -d '{
    "budget_id": "free-tier",
    "max_budget": 1,
    "tpm_limit": 5,
    "rpm_limit": 2
  }'

# Attach to customer
curl 'http://0.0.0.0:4000/customer/new' \
  -d '{
    "user_id": "palantir",
    "budget_id": "free-tier"
  }'

# Client usage — pass `user` in chat request
curl http://localhost:4000/chat/completions \
  -H 'Authorization: Bearer sk-...' \
  -d '{
    "model": "gpt-4o",
    "user": "palantir",
    "messages": [{"role": "user", "content": "hi"}]
  }'
```

## Agent budgets (Agent SDK / A2A)

Per-agent rate limits + session caps:

```bash
curl 'http://localhost:4000/v1/agents' \
  -H 'Authorization: Bearer $MASTER' \
  -d '{
    "agent_name": "pubmed-research-agent",
    "agent_card_params": {
      "name": "pubmed-research-agent",
      "description": "Biomedical research agent",
      "url": "http://pubmed-mcp:8080",
      "version": "1.0.0"
    },
    "tpm_limit": 100000,
    "rpm_limit": 100,
    "session_tpm_limit": 50000,
    "session_rpm_limit": 50,
    "litellm_params": {
      "max_iterations": 25,
      "max_budget_per_session": 5.00
    }
  }'
```

Update:

```bash
curl -X PATCH 'http://localhost:4000/v1/agents/<agent_id>' \
  -d '{"tpm_limit": 200000, "rpm_limit": 200}'
```

## Budget duration format

| Unit | Example | Meaning    |
| ---- | ------- | ---------- |
| s    | `30s`   | 30 seconds |
| m    | `30m`   | 30 minutes |
| h    | `30h`   | 30 hours   |
| d    | `30d`   | 30 days    |
| mo   | `1mo`   | 1 month    |

Reset scheduler config:

```yaml
general_settings:
  proxy_budget_rescheduler_min_time: 1 # min seconds between checks
  proxy_budget_rescheduler_max_time: 1 # max seconds
```

Default scheduler polls every 10 minutes.

## Rate limits (TPM / RPM)

Applies at all scopes (key, user, team, per-model).

### Per-key

```bash
curl 'http://0.0.0.0:4000/key/generate' \
  -d '{
    "max_parallel_requests": 10,
    "tpm_limit": 20,
    "rpm_limit": 4
  }'
```

### Per-key per-model

```bash
curl 'http://0.0.0.0:4000/key/generate' \
  -d '{
    "model_rpm_limit": {"gpt-4": 2},
    "model_tpm_limit": {"gpt-4": 1000}
  }'
```

### Per-team per-model

```bash
curl 'http://0.0.0.0:4000/team/new' \
  -d '{
    "team_id": "prod",
    "model_rpm_limit": {"gpt-4": 100, "gpt-3.5-turbo": 200},
    "model_tpm_limit": {"gpt-4": 10000, "gpt-3.5-turbo": 20000}
  }'
```

### Response headers (remaining capacity)

```
x-litellm-key-remaining-requests-gpt-4: 1
x-litellm-key-remaining-tokens-gpt-4: 179
```

Useful for client-side backoff.

## TPM counting mode

```yaml
general_settings:
  token_rate_limit_type: "total" # total | input | output
```

- `total` (default): prompt + completion
- `input`: prompt only
- `output`: completion only

## Spend tracking endpoints

```bash
# Key-level
curl 'http://0.0.0.0:4000/key/info?key=<key>' -H "Authorization: Bearer $MASTER"

# User-level
curl 'http://0.0.0.0:4000/user/info?user_id=<user_id>' -H "Authorization: Bearer $MASTER"

# Team-level
curl 'http://0.0.0.0:4000/team/info?team_id=<team_id>' -H "Authorization: Bearer $MASTER"

# All spend logs (audit)
curl 'http://0.0.0.0:4000/spend/logs' -H "Authorization: Bearer $MASTER"

# Filter by date
curl 'http://0.0.0.0:4000/spend/logs?start_date=2026-04-01&end_date=2026-04-14' \
  -H "Authorization: Bearer $MASTER"

# Per-user spend report
curl 'http://0.0.0.0:4000/global/spend/report?api_key=<key>' \
  -H "Authorization: Bearer $MASTER"
```

Response includes `spend` (USD), `model`, `cache_hit`, `usage.total_tokens`, `metadata`.

## Temporary budget increase

```bash
curl 'http://localhost:4000/key/update' \
  -d '{
    "key": "sk-...",
    "temp_budget_increase": 100,
    "temp_budget_expiry": "10d"
  }'
```

Original budget restored after expiry.

## Alerts (Slack / PagerDuty)

```yaml
general_settings:
  alerting: ["slack"]
  alerting_threshold: 300
  alert_types:
    - budget_alerts
    - llm_exceptions
    - db_exceptions
  alert_to_webhook_url:
    budget_alerts: "https://hooks.slack.com/..."
```

Env: `SLACK_WEBHOOK_URL`. Alerts fire at 50%, 75%, 90%, 100% of budget.

## Soft budget

```bash
curl 'http://0.0.0.0:4000/key/generate' \
  -d '{
    "max_budget": 100,
    "soft_budget": 80
  }'
```

Soft budget triggers alert without blocking. Useful for early warning.

## Disable budget checks for admins

Admin users bypass rate limits by default. Test enforcement with `internal_user` role.

## IntelliSoins usage pattern

- Team `pubmed-agents`: $500/mo, rpm 1000, tpm 100k
- Team `masterai`: $200/mo, rpm 500
- Per-agent: $5/session cap, max_iterations 25
- Alerts Slack `#alerts-litellm` à 75% + 100%
- Monthly spend report via cron → email Michael

## Source

docs.litellm.ai/docs/proxy/users + budgets + spend — scraped 2026-04-14.
