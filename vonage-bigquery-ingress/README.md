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
2. **`GET /v2/reports/{request_id}`** — poll until `request_status` is `SUCCESS` (or `FAILED`/`ABORTED`/`TRUNCATED` — log and skip those). **Reports are only retrievable for 4 days** after creation — after that the request itself is gone, not just the download link.
3. **`GET /v3/media/{file_id}`** (from `_links.download_report.href`) — downloads a **zip** containing one CSV. Available for 72 hours (a separate, shorter window inside the 4-day report retention).

Rate limits: 5 req/s async, 10 req/s sync.

**Auth confirmed with Vonage support (2026-08-18):** a *secondary* API key is explicitly the wrong tool here — it shares the same balance/pricing/routing as the primary key and exists for credential separation, not billing automation. Use the **primary** account's API key/secret (what `main.py` already expects via `VONAGE_API_KEY`/`VONAGE_API_SECRET`). Support also confirmed: for postpaid accounts, invoices land in the primary account email monthly (first week of the month) and are downloadable from the Customer Dashboard under Billing > Payments > Payment History — that manual path still exists as a fallback/cross-check alongside this pipeline.

**Full product list** (per Vonage's API reference, wider than what this pipeline currently pulls): `SMS`, `SMS-TRAFFIC-CONTROL`, `VOICE-CALL`, `VOICE-FAILED`, `VOICE-TTS`, `IN-APP-VOICE`, `WEBSOCKET-CALL`, `ASR`, `AMD`, `VERIFY-API`, `VERIFY-V2`, `NUMBER-INSIGHT`, `CONVERSATION-EVENT`, `CONVERSATION-MESSAGE`, `MESSAGES`, `VIDEO-API`, `NETWORK-API-EVENT`, `REPORTS-USAGE`. `VONAGE_PRODUCTS` currently only requests `SMS,VOICE-CALL,VOICE-TTS,WEBSOCKET-CALL` — check a real invoice once credentials exist to confirm nothing else is billed (e.g. `VERIFY-API` if 2FA is in use).

### CSV schema — confirmed for SMS, unconfirmed for everything else

Vonage's docs give a full example row for **SMS** reports:
`account_id, message_id, account_ref, client_ref, direction, from, to, forced_from, changed_from, concatenated, message_body, network, network_name, country, country_name, date_received, date_finalized, latency, status, error_code, error_code_description, currency, total_price, id, dcs, validity_period, ip_address, udh, workflow_id, tier_volume`

**Voice (`VOICE-CALL`) and WebSocket (`WEBSOCKET-CALL`) CSV columns are not documented publicly** and this pipeline hasn't pulled a real sample yet (no credentials during initial build — see Status below). `cloud_run_job/main.py` is written defensively for this: a handful of well-known SMS-style field names are promoted to typed BigQuery columns (`total_price`, `currency`, `network`, `country`, `status`, `direction`), everything else is preserved as-is in a `raw` JSON column so no data is lost regardless of what the actual Voice/WebSocket columns turn out to be. **Once real credentials exist, pull one real report per product and check `raw` against the column list above — promote more fields to typed columns if useful, and confirm the dedup-key field (`message_id` for SMS; unconfirmed for Voice/WebSocket, see below).**

### What this API does NOT cover

The manual traffic-report CSVs (see the SKU categorization below) include **number rental charges** (`Long Code Numbers`, `Toll-free Numbers` — recurring, not usage-based) and other non-CDR line items. The Reports API is CDR/usage-only — it will not have these. Number rental charges need to keep coming from the manual invoice CSVs (or from a separate Vonage billing/invoice API, not investigated here) — this pipeline does not replace that.

---

## Part 2 — GCP side: service account, Secret Manager, BigQuery target

1. **Service account** `vonage-importer@<GCP_PROJECT_ID>.iam.gserviceaccount.com` — the Cloud Run Job's execution identity. Needs `roles/secretmanager.secretAccessor` (to read the Vonage credentials) and `roles/bigquery.dataEditor` + `roles/bigquery.jobUser` (same pattern as the AWS pipeline).

2. **Secret Manager** holds the Vonage credentials as a single secret, `vonage-master-api-keys` — a JSON blob shaped exactly like the telephony service's existing `vonage-creds-telephony-service` secret in `prj-ufonia-prd-lon-svc-01` (`VONAGE_API_KEY`, `VONAGE_API_SECRET`, `VONAGE_APP_ID`, `VONAGE_PRIVATE_KEY`, `VONAGE_SIGNATURE_SECRET`) — this pipeline only reads the first two. **Decided 2026-08-18:** rather than a cross-project read of the telephony service's secret, or the pipeline's own separate `vonage-api-key`/`vonage-api-secret` string secrets (an earlier design, now removed — see git history), the real credential value is duplicated once into this project's own `vonage-master-api-keys` secret. Terraform creates the **container only** (`google_secret_manager_secret`) — it deliberately does **not** create a secret version, so no credential material ever touches Terraform state or this repo. To (re)populate it:

   ```sh
   gcloud secrets versions access latest --secret=vonage-creds-telephony-service --project=<TELEPHONY_SERVICE_PROJECT_ID> \
     | gcloud secrets versions add vonage-master-api-keys --data-file=- --project=<GCP_PROJECT_ID>
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

**Credentials:** the job reads `VONAGE_CREDS_JSON` — the whole `vonage-master-api-keys` secret value, injected as one env var by Cloud Run — and parses out `VONAGE_API_KEY`/`VONAGE_API_SECRET`. `VONAGE_ACCOUNT_ID` defaults to the API key itself (confirmed against real data: the primary account's own `api_key` works as `account_id`) — set it explicitly to pull a subaccount instead.

---

## Part 5 — Deployment (`terraform/run.tf`)

Same shape as `aws-bigquery-ingress`'s Part 5:

- **Image**: built with `docker buildx build --platform linux/amd64 -t europe-west2-docker.pkg.dev/prj-ufonia-dev-lon-svc-01/ufonia/vonage-bigquery-import:<tag> --push .` from `cloud_run_job/`, pushed to the same centralized `ufonia` Artifact Registry repo the AWS pipeline uses.
- **Cross-project image pull**: the billing project's Cloud Run service agent (`service-<PROJECT_NUMBER>@serverless-robot-prod.iam.gserviceaccount.com`) needs `roles/artifactregistry.reader` on the `ufonia` repo — `google_artifact_registry_repository_iam_member.vonage_importer_image_pull`.
- **Cloud Run Job** `vonage-bigquery-import` (not a Service), execution identity = the `vonage_importer` SA, deployed via `google_cloud_run_v2_job.vonage_bigquery_import` with `image_tag` passed at apply time (`terraform apply -var="image_tag=<tag just pushed>"`). The Vonage credential is injected via `env { value_source { secret_key_ref { secret = ... } } } }` pointing at `vonage-master-api-keys` — never a plain-value env var.
- **Cloud Scheduler** (`vonage-bigquery-import-daily`, `0 7 * * *` UTC — an hour after the AWS pipeline's 06:00 UTC run, to stagger them) hits the Cloud Run Jobs `run` API via a dedicated `vonage-scheduler-invoker` SA holding `roles/run.invoker` on just this job.
- **Manual re-run**: `gcloud run jobs execute vonage-bigquery-import --region=europe-west2 --project=prj-ufonia-cmn-lon-billing-01 --wait`.
- **Monitoring**: not yet set up — same gap as the AWS pipeline (alert on exit code ≠ 0, freshness check on `MAX(usage_date)`).

---

## Status

- ✅ Part 1: API flow, auth, and full CSV schema (SMS, VOICE-CALL, VOICE-TTS, WEBSOCKET-CALL) confirmed against **real production data** (2026-08-18), using the existing `vonage-creds-telephony-service` secret in `prj-ufonia-prd-lon-svc-01` (same primary-account API key/secret the telephony service already uses — Vonage support confirmed a secondary key is the wrong tool for this).
- ✅ Part 2: Terraform written and applied (service account, Secret Manager containers, BigQuery dataset/table).
- ✅ Part 3: `cloud_run_job/main.py` written, **run successfully end-to-end** against real data and the live `vonage_cost_and_usage` table. Fixed two real bugs found during that test run:
  - `VOICE-TTS` and `WEBSOCKET-CALL` reject the `direction` parameter (422) — the job previously looped `direction` for every product, so it silently loaded **zero rows** for these two. Fixed: `PRODUCTS_WITH_DIRECTION = {"SMS", "VOICE-CALL"}` gates which products get the direction loop; the other two are requested once with no `direction`.
  - `DATE_FIELDS` had a nonexistent `"date_start_time"` field name; the real column is `date_start` (VOICE-CALL/WEBSOCKET-CALL) or `creation_date` (VOICE-TTS). Fixed.
  - `RECORD_ID_FIELDS` needed no change — `message_id` (SMS), `call_id` (VOICE-CALL/WEBSOCKET-CALL), and the `id` fallback (VOICE-TTS, which has no `message_id`/`call_id`) all resolved correctly as-is.
  - Confirmed real row counts/totals landed correctly in BigQuery for a 2-day lookback (SMS, VOICE-CALL in/out, WEBSOCKET-CALL — VOICE-TTS returned 0 rows for that window, but the request itself succeeded).
- ✅ **Credential sourcing decided and done (2026-08-18):** the two earlier unused `vonage-api-key`/`vonage-api-secret` secret containers were removed from Terraform; `vonage-master-api-keys` (a JSON blob, same shape as `vonage-creds-telephony-service`) was added and populated with the real primary-account credential. `main.py` now reads `VONAGE_CREDS_JSON` and parses out the key/secret. Verified with a real 1-day report request against the new secret.
- ✅ **Backfilled the full year to date:** `vonage_cost_and_usage` has continuous coverage 2026-01-01 through 2026-08-17 (229/229 days) via manual one-off pulls (see memory `project-vonage-reports-api-plan` for the process — fetch credentials, throwaway venv, run `main.py`'s functions with a custom date range, clean up).
- ✅ **Part 5 deployed (2026-08-18):** Cloud Run Job (`vonage-bigquery-import`) + daily Cloud Scheduler trigger (`vonage-bigquery-import-daily`, `0 7 * * *` UTC) via `terraform/run.tf`, same pattern as `aws-bigquery-ingress`'s Part 5 — image built with `docker buildx build --platform linux/amd64` and pushed to the shared `ufonia` Artifact Registry repo (`europe-west2-docker.pkg.dev/prj-ufonia-dev-lon-svc-01/ufonia/vonage-bigquery-import`), cross-project image-pull IAM for Cloud Run's service agent, a dedicated `vonage-scheduler-invoker` SA with `roles/run.invoker` on just this job. The job reads `VONAGE_CREDS_JSON` straight from the `vonage-master-api-keys` secret via `value_source.secret_key_ref` — no credential ever passed as a plain env var value in Terraform. **Manually executed and verified**: `gcloud run jobs execute --wait` completed successfully (exit 0), logs showed the expected per-product/direction row counts, and `vonage_cost_and_usage`'s total row count was unchanged after the run (1,397,326) — confirming the `MERGE` dedup re-updated the existing lookback window instead of duplicating it, running for real from the deployed container rather than the local script used for every prior pull. The 07:00 UTC daily schedule itself hasn't self-triggered yet (first natural firing is tomorrow).
- ⬜ Not started: wiring into the `billing-dashboard` skill; freshness-check alerting (e.g. a scheduled query asserting `MAX(usage_date)` stays within the last ~2 days) — the same gap the AWS pipeline's own Part 5 still has, not yet built there either.

**Before relying on the schedule unattended:** check the fuller Reports API product list (see Part 1) against a real invoice — currently only `SMS,VOICE-CALL,VOICE-TTS,WEBSOCKET-CALL` are pulled — and confirm tomorrow's 07:00 UTC run fires on its own.
