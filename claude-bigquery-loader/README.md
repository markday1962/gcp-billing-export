# Importing Claude API Usage & Cost into BigQuery — Setup Guide

Tracks Ufonia's own Anthropic/Claude API spend (Console/API platform, not Claude Enterprise) alongside the AWS/GCP/Vonage cost pipelines in this repo, using Anthropic's **Usage & Cost Admin API**.

Placeholders to swap for real values: `<GCP_PROJECT_ID>`, `<ANTHROPIC_ADMIN_KEY>`.

---

## Part 1 — The Usage & Cost Admin API

Base URL `https://api.anthropic.com`, header auth: `x-api-key: <ANTHROPIC_ADMIN_KEY>` + `anthropic-version: 2023-06-01`. Requires an **Admin API key** (`sk-ant-admin01-...`), not a regular API key — create one in Console with the narrowest scope available (read-only usage/cost), not full org-admin rights, since Admin API keys can otherwise manage users/workspaces/keys org-wide.

### `GET /v1/organizations/usage_report/messages` — token usage

Query params: `starting_at` (required, RFC 3339), `ending_at`, `bucket_width` (`1m`/`1h`/`1d`), `group_by[]` (`model`, `workspace_id`, `api_key_id`, `service_tier`, `context_window`, `inference_geo`, `account_id`, `service_account_id`, `speed` — the last needs beta header `fast-mode-2026-02-01`), plus matching `models[]`/`workspace_ids[]`/etc. filters, `limit`, `page`.

Response — one entry per time bucket, each with a `results` array (one row per unique combination of the requested `group_by` dimensions):

```json
{
  "data": [{
    "starting_at": "2025-08-01T00:00:00Z",
    "ending_at": "2025-08-02T00:00:00Z",
    "results": [{
      "account_id": "user_...", "api_key_id": "apikey_...", "workspace_id": "wrkspc_...",
      "service_account_id": "svac_...", "model": "claude-opus-4-6",
      "service_tier": "standard", "context_window": "0-200k", "inference_geo": "global",
      "uncached_input_tokens": 1500, "cache_read_input_tokens": 200,
      "cache_creation": {"ephemeral_5m_input_tokens": 500, "ephemeral_1h_input_tokens": 1000},
      "output_tokens": 500, "server_tool_use": {"web_search_requests": 10}
    }]
  }],
  "has_more": true, "next_page": "page_..."
}
```

**No single "total input tokens" field** — sum `uncached_input_tokens` + `cache_read_input_tokens` + both `cache_creation.*` fields yourself if you want one.

### `GET /v1/organizations/cost_report` — USD cost

Query params: `starting_at` (required), `ending_at`, `bucket_width` (`1d` **only** — no finer granularity), `group_by[]` (`workspace_id`, `description` — not `model` directly; model/inference_geo/etc. arrive as sibling fields only when grouping by `description`), `limit`, `page`.

```json
{
  "data": [{
    "starting_at": "2025-08-01T00:00:00Z", "ending_at": "2025-08-02T00:00:00Z",
    "results": [{
      "amount": "123.78912", "currency": "USD",
      "description": "Claude Sonnet 4 Usage - Input Tokens",
      "cost_type": "tokens", "token_type": "uncached_input_tokens",
      "model": "claude-opus-4-6", "service_tier": "standard",
      "context_window": "0-200k", "inference_geo": "global",
      "workspace_id": "wrkspc_..."
    }]
  }],
  "has_more": true, "next_page": "page_..."
}
```

`workspace_id: null` means the default workspace. `cost_type` ∈ `tokens`/`web_search`/`code_execution`/`session_usage`. **Priority Tier costs are excluded from this endpoint entirely** — track those via the usage endpoint's `service_tier=priority` filter instead.

**⚠️ Open item: `amount`'s scale is unconfirmed.** The docs describe it as "lowest currency units (cents)" but the documented example (`"123.78912"`) reads far more naturally as $123.79 than $1.24. This pipeline stores `amount` as-is (assumed to already be dollars) — **verify against a real cost total once a key exists, before trusting `claude_cost.amount_usd`.**

Both endpoints: `has_more`/`next_page` pagination. Data freshness ~5 min; poll at most once/minute for sustained use.

---

## Part 2 — GCP side: service account, Secret Manager, BigQuery target

Same shape as `vonage-bigquery-loader/`: service account `claude-importer@<GCP_PROJECT_ID>.iam.gserviceaccount.com`, a Secret Manager **container only** (`claude-admin-api-key` — no version created by Terraform, add the real key yourself):

```sh
echo -n "<ANTHROPIC_ADMIN_KEY>" | gcloud secrets versions add claude-admin-api-key --data-file=- --project=<GCP_PROJECT_ID>
```

Two BigQuery tables (see `terraform/gcp.tf` for the exact schema), both partitioned by `usage_date`:

- **`claude_usage`** — one row per (day, model, workspace) from the usage endpoint, requested with `group_by=[model, workspace_id]`. No natural unique ID (these are aggregates, not events) — deduped on a hash of `usage_date` + every dimension field, same pattern used for Vonage's unverified-schema rows.
- **`claude_cost`** — one row per (day, workspace, description) from the cost endpoint, requested with `group_by=[workspace_id, description]`. Deduped the same way.

---

## Part 3 — The Cloud Run Job

`cloud_run_job/main.py`: for each of the two endpoints, requests a rolling `LOOKBACK_DAYS`-day window (default 4, to catch any late-finalized cost corrections), pages through `has_more`/`next_page`, flattens each bucket's `results` into rows, loads into a staging table, `MERGE`s into the target table keyed on the hashed `record_id`.

---

## Status

- ✅ Part 1: both endpoints' exact request/response shapes confirmed from Anthropic's docs (not guessed).
- ✅ Part 2: Terraform written — **not yet applied** (unlike the AWS/Vonage pipelines, this one wasn't run against GCP yet; do that before Part 3 can actually load anything).
- ✅ Part 3: `cloud_run_job/main.py` written, **not yet run against a real Admin API key** — no key exists yet.
- ⬜ Not started: applying Terraform, adding the real Admin API key to Secret Manager, a real test pull (in particular to resolve the `amount` scale open item above), Cloud Run Job + Scheduler deployment, wiring into the `billing-dashboard` skill.
