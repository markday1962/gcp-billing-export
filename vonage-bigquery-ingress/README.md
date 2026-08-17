# Automating Vonage Costs into BigQuery — Setup Guide

Replaces the manual process of dropping Vonage/Nexmo traffic-report CSVs into this folder by hand. Uses the **Vonage Reports API** (CDR-level, one row per SMS/call) rather than the "self-serve Traffic Report" dashboard feature — see [[project-vonage-reports-api-plan]] in memory for why, and `../aws-bigquery-ingress/README.md` for the sibling AWS pipeline this one is modeled on.

Placeholders to swap for real values: `<GCP_PROJECT_ID>`, `<VONAGE_ACCOUNT_ID>`, `<VONAGE_API_KEY>`, `<VONAGE_API_SECRET>`.

---

## How it differs from the AWS pipeline

The AWS pipeline (`aws-bigquery-ingress/`) uses keyless OIDC federation because AWS supports it. Vonage's Reports API only supports HTTP Basic Auth (API key:secret) — there's no keyless option, so this pipeline stores the Vonage credentials in **Google Secret Manager** instead, and the Cloud Run Job reads them as injected env vars. Otherwise the shape is the same: Terraform for the GCP side (service account, BigQuery dataset/table, Cloud Run Job, Cloud Scheduler), a Python script for the actual import logic.

---

## Part 1 — The Vonage Reports API

Endpoints (base `https://api.nexmo.com`), all HTTP Basic Auth (`base64(api_key:api_secret)`):

1. **`POST /v2/reports`** — request an async report. Body: `product` (one of `SMS`, `VOICE-CALL`, `VOICE-TTS`, `WEBSOCKET-CALL`, and others — **one product per request**, not a list), `account_id`, `direction` (`inbound` or `outbound`), `date_start`/`date_end` (ISO 8601). Returns `{request_id, request_status, _links: {self, download_report}}`.
2. **`GET /v2/reports/{request_id}`** — poll until `request_status` is `SUCCESS` (or `FAILED`/`ABORTED`/`TRUNCATED` — log and skip those).
3. **`GET /v3/media/{file_id}`** (from `_links.download_report.href`) — downloads a **zip** containing one CSV. Available for 72 hours.

Rate limits: 5 req/s async, 10 req/s sync.

### CSV schema — confirmed for SMS, unconfirmed for everything else

Vonage's docs give a full example row for **SMS** reports:
`account_id, message_id, account_ref, client_ref, direction, from, to, forced_from, changed_from, concatenated, message_body, network, network_name, country, country_name, date_received, date_finalized, latency, status, error_code, error_code_description, currency, total_price, id, dcs, validity_period, ip_address, udh, workflow_id, tier_volume`

**Voice (`VOICE-CALL`) and WebSocket (`WEBSOCKET-CALL`) CSV columns are not documented publicly** and this pipeline hasn't pulled a real sample yet (no credentials during initial build — see Status below). `cloud_run_job/main.py` is written defensively for this: a handful of well-known SMS-style field names are promoted to typed BigQuery columns (`total_price`, `currency`, `network`, `country`, `status`, `direction`), everything else is preserved as-is in a `raw` JSON column so no data is lost regardless of what the actual Voice/WebSocket columns turn out to be. **Once real credentials exist, pull one real report per product and check `raw` against the column list above — promote more fields to typed columns if useful, and confirm the dedup-key field (`message_id` for SMS; unconfirmed for Voice/WebSocket, see below).**

### What this API does NOT cover

The manual traffic-report CSVs (see the SKU categorization below) include **number rental charges** (`Long Code Numbers`, `Toll-free Numbers` — recurring, not usage-based) and other non-CDR line items. The Reports API is CDR/usage-only — it will not have these. Number rental charges need to keep coming from the manual invoice CSVs (or from a separate Vonage billing/invoice API, not investigated here) — this pipeline does not replace that.

---

## Part 2 — GCP side: service account, Secret Manager, BigQuery target

1. **Service account** `vonage-importer@<GCP_PROJECT_ID>.iam.gserviceaccount.com` — the Cloud Run Job's execution identity. Needs `roles/secretmanager.secretAccessor` (to read the Vonage credentials) and `roles/bigquery.dataEditor` + `roles/bigquery.jobUser` (same pattern as the AWS pipeline).

2. **Secret Manager** holds the Vonage API key and secret. Terraform creates the **secret containers only** (`google_secret_manager_secret`) — it deliberately does **not** create a secret version, so no credential material ever touches Terraform state or this repo. Add the real values yourself once you have them:

   ```sh
   echo -n "<VONAGE_API_KEY>" | gcloud secrets versions add vonage-api-key --data-file=- --project=<GCP_PROJECT_ID>
   echo -n "<VONAGE_API_SECRET>" | gcloud secrets versions add vonage-api-secret --data-file=- --project=<GCP_PROJECT_ID>
   ```

3. **BigQuery dataset/table** — see `terraform/gcp.tf` for the exact schema. Partitioned by `usage_date`, deduped by `record_id` (see the dedup-key note below), with a `category` column matching the manual traffic report's existing scheme (`SMS`, `Inbound Calls`, `Outbound Calls`, `WebSocket`, `Other`) so this can slot into the same dashboard queries once it's live.

---

## Part 3 — The Cloud Run Job

`cloud_run_job/main.py`:

1. For each `(product, direction)` pair in `VONAGE_PRODUCTS` × `("inbound", "outbound")`: `POST /v2/reports`, poll `GET /v2/reports/{id}` until `SUCCESS`, download and unzip the CSV via `GET` on the `download_report` link.
2. Parse each CSV row. Derive:
   - `usage_date` from `date_received` (SMS) — **unconfirmed for Voice/WebSocket**, falls back to the request's `date_start` if no date field is found in the row.
   - `record_id` — first present of `message_id`, `call_id`, `uuid`, `id` (in that order); **the Voice/WebSocket unique-ID field name is unconfirmed** — if none of these are present, falls back to a hash of the full row, which is not a stable dedup key across restatements and needs fixing once a real Voice sample is seen.
   - `category` — `SMS` for the SMS product; for `VOICE-CALL`, `Inbound Calls`/`Outbound Calls` by direction; `WebSocket` for `WEBSOCKET-CALL`; `Other` for everything else.
   - `total_price`, `currency`, `network`, `country`, `status`, `direction` promoted to typed columns when present; the full raw row also goes into a `raw` JSON column.
3. Load into a staging table, `MERGE` into `vonage_cost_and_usage` keyed on `(usage_date, record_id)`.

**Default product list** (`VONAGE_PRODUCTS` env var, comma-separated): `SMS,VOICE-CALL,VOICE-TTS,WEBSOCKET-CALL` — covers what the manual traffic report's usage-based SKUs map to. Extend it if the account bills for other Reports API products (see the full list in Part 1).

---

## Status

- ✅ Part 1: API flow, auth, and SMS CSV schema confirmed from Vonage's docs.
- ✅ Part 2: Terraform written (service account, Secret Manager containers, BigQuery dataset/table).
- ✅ Part 3: `cloud_run_job/main.py` written, defensively designed for the unconfirmed Voice/WebSocket schema — **not yet run against a real report**, since no Vonage API credentials were available during the initial build.
- ⬜ Not started: adding the real credentials to Secret Manager, deploying the Cloud Run Job + Scheduler (mirroring `aws-bigquery-ingress`'s Part 5), pulling a real Voice/WebSocket sample and correcting the schema/dedup-key against it, wiring into the `billing-dashboard` skill.

**Before deploying:** get real Vonage credentials, add them to Secret Manager (Part 2, step 2), then run the Cloud Run Job manually once and inspect the `raw` column in BigQuery for the Voice/WebSocket rows — correct the field-name assumptions in `main.py` (`RECORD_ID_FIELDS`, `DATE_FIELDS`) based on what's actually there before turning on the daily schedule.
