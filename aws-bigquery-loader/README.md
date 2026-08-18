# Importing AWS Costs into BigQuery — Setup Guide

A lightweight, keyless pipeline: AWS Cost and Usage Report (CUR) data lands in S3, a scheduled Cloud Run Job picks it up using short-lived AWS credentials obtained via OIDC federation (no AWS access key stored anywhere in GCP), and loads it into BigQuery.

Placeholders to swap for real values throughout: `<AWS_ACCOUNT_ID>`, `<CUR_BUCKET>`, `<GCP_PROJECT_ID>`, `<GCP_PROJECT_NUMBER>`, `<BQ_DATASET>`, `<BQ_TABLE>`, `<REGION>`.

---

## Part 1 — AWS side: export cost data to S3

1. **Enable a cost export.** In the AWS Billing console, go to *Data Exports* (the successor to the legacy CUR 1.0 console — CUR 2.0 exports are configured the same way). Create a new export:
   - Table: *Cost and Usage Report* (standard) — includes resource IDs if you want per-resource granularity.
   - Format: **CSV, gzip compressed**, alongside a `Manifest.json` per refresh describing the report period and column list. (Parquet is smaller/faster to load and preserves types if your export supports it — the `cost-by-environment` export here produces CSV.gz, so the rest of this guide targets that.)
   - Time granularity: daily.
   - Destination: a dedicated S3 bucket, e.g. `<CUR_BUCKET>`, in a prefix like `cur/aws-cost-export/`.
   - Overwrite behaviour: AWS re-writes/restates the current and prior billing period as usage gets finalized (refunds, credits, delayed usage records land up to a few days late) — observed here as the same report period (e.g. `20260801-20260901`) being re-exported to a new timestamped folder roughly twice a day. Your load logic needs to handle this — see Part 4.

2. **Bucket policy.** No special policy is needed yet beyond default AWS Billing export permissions — the IAM role in Part 2 will be granted read access directly.

3. Wait for the first export to land (can take several hours after creation) and confirm the CSV.gz + `Manifest.json` files appear in the bucket before moving on.

   ✅ Confirmed for `cost-by-environment`: files are landing under
   `cost-by-environment/cost-by-environment/<period>/<timestamp>/cost-by-environment-00001.csv.gz`
   with a sibling `cost-by-environment-Manifest.json`.

---

## Part 2 — AWS side: let a GCP service account assume a role (no static keys)

This is the piece that avoids ever storing an AWS access key/secret in GCP. GCP service accounts can generate signed OIDC ID tokens; AWS STS can accept those via `AssumeRoleWithWebIdentity` if you register Google as an identity provider.

1. **Create the GCP service account first** (see Part 3, step 1) — you need its unique numeric ID and email before setting up the AWS trust policy.

2. **Register Google as an OIDC identity provider in AWS IAM:**
   - Provider URL: `https://accounts.google.com`
   - Audience: the GCP service account's **numeric OAuth client ID** (its `unique_id`), **not its email**. This is the one genuinely non-obvious gotcha in this whole setup — see the callout below.

   > ⚠️ **`aud` vs `azp`:** you *request* an ID token with `audience = <service account email>`, and that string does show up in the token's `aud` claim — but the metadata server also stamps every service-account ID token with an `azp` claim set to the calling SA's numeric OAuth client ID. Per AWS's own docs: *"If your OIDC identity provider is setting both `aud` and `azp` claims in the token, AWS STS will use the value in the `azp` claim as the `aud` claim."* So AWS actually matches against `azp` (the numeric ID), not the literal `aud` string. Registering the SA's **email** as the audience/client ID — which is what nearly every blog post and even the AWS console UI's "Audience" field wording implies you should do — passes signature/issuer validation just fine and then fails every single `AssumeRoleWithWebIdentity` call with a generic `InvalidIdentityToken`, with no indication of why. Decode a real token (`https://oauth2.googleapis.com`-signed JWT, base64-decode the payload) to confirm its `azp` value, or read it straight off the SA's details page in the GCP console ("OAuth 2 Client ID").

3. **Create an IAM role** (e.g. `cur-bigquery-import-role`) with a trust policy scoped tightly to that one service account:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Principal": { "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/accounts.google.com" },
       "Action": "sts:AssumeRoleWithWebIdentity",
       "Condition": {
         "StringEquals": {
           "accounts.google.com:aud": "<GCP_SERVICE_ACCOUNT_UNIQUE_ID>"
         }
       }
     }]
   }
   ```

4. **Attach a narrow permissions policy** to the role — read-only, scoped to just the CUR bucket:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["s3:GetObject", "s3:ListBucket"],
       "Resource": [
         "arn:aws:s3:::<CUR_BUCKET>",
         "arn:aws:s3:::<CUR_BUCKET>/*"
       ]
     }]
   }
   ```

Note the credential minted this way is valid for up to 1 hour and only exists in the Cloud Run Job's memory during the run — nothing to rotate, nothing to leak.

---

## Part 3 — GCP side: service account and BigQuery target

1. **Create a dedicated service account**, e.g. `cur-importer@<GCP_PROJECT_ID>.iam.gserviceaccount.com`. This is the identity the Cloud Run Job runs as, and the same identity AWS's trust policy above references.

2. **Grant it BigQuery roles** on the target project/dataset — `roles/bigquery.dataEditor` on `<BQ_DATASET>` and `roles/bigquery.jobUser` on `<GCP_PROJECT_ID>` (nothing broader is needed).

3. **Create the destination table**, partitioned by usage date, e.g.:

   ```sql
   CREATE TABLE `<GCP_PROJECT_ID>.<BQ_DATASET>.<BQ_TABLE>`
   PARTITION BY usage_date
   AS SELECT * FROM UNNEST([]) -- or define an explicit schema up front from the CUR Parquet schema
   ```

   Partitioning by usage date is what makes the restatement handling in Part 4 cheap (partition overwrite instead of full-table rewrite).

---

## Part 4 — The Cloud Run Job

**Trigger:** Cloud Scheduler → Cloud Run Jobs API, daily (e.g. 06:00 UTC, a few hours after the AWS export typically refreshes).

**Logic, roughly:**

1. Mint a Google ID token for the service account with `audience = cur-importer@<GCP_PROJECT_ID>.iam.gserviceaccount.com` (use `google.auth` — this works automatically inside Cloud Run using the attached service account, no key file needed).
2. Call AWS STS `assume_role_with_web_identity` with that token, the role ARN from Part 2, and a role session name — get back temporary AWS credentials (access key, secret, session token, ~1hr TTL).
3. Use `boto3` with those temporary credentials to fetch the "current" manifest for each billing period being watched — `{prefix}/{report_name}/{period}/{report_name}-Manifest.json`. AWS Data Exports keeps this manifest pointed at the latest assembly's `reportKeys`, so there's no need to list timestamped folders or diff against previous runs.
4. Download and gunzip each file in `reportKeys`, parse the CSV, project/rename the columns we care about, and load the rows into a **staging table** in BigQuery (`bigquery.Client.load_table_from_json` with an explicit `SchemaField` list and `WRITE_TRUNCATE` — simplest option at this file size; no need for `load_table_from_uri`/GCS staging).
5. Run a `MERGE` from staging into `<BQ_TABLE>`, keyed on `usage_date` + `line_item_id` (CUR's `identity/LineItemId`, unique per file), so a restated day cleanly replaces the prior version rather than duplicating rows. Re-check the previous billing period for the first `RESTATEMENT_WINDOW_DAYS` days of a new month to catch AWS's restatement of the prior period.
6. Log a summary (rows loaded, assembly ID, target table) to stdout — Cloud Run Job logs flow to Cloud Logging automatically. Add a log-based alert on job failure so you notice if AWS changes export format or the trust relationship breaks.

**Real, working implementation:** [`cloud_run_job/main.py`](cloud_run_job/main.py) (plus `requirements.txt` and `Dockerfile` in the same folder). Verified locally against a real downloaded CUR file — parses cleanly, `line_item_id` is unique per file, and `resource_tags_environment` carries real per-customer environment names (confirming this is what the `cost-by-environment` bucket is for).

---

## Part 5 — Deployment checklist

- Container: a minimal Python image (`google-cloud-bigquery`, `boto3`, `google-auth`). Built with `docker buildx build --platform linux/amd64` (needed on Apple Silicon dev machines — Cloud Run runs amd64) and pushed to the centralized Artifact Registry repo at `europe-west2-docker.pkg.dev/prj-ufonia-dev-lon-svc-01/ufonia/cur-bigquery-import:<tag>`, tagged with a UTC build timestamp.
- Cross-project image pull: since the image lives in a different project than the Cloud Run Job, the billing project's Cloud Run service agent (`service-<PROJECT_NUMBER>@serverless-robot-prod.iam.gserviceaccount.com`) needs `roles/artifactregistry.reader` on the `ufonia` repo — see `google_artifact_registry_repository_iam_member.cur_importer_image_pull` in `terraform/run.tf`.
- Cloud Run Job (not a Service — this is a batch task, not something serving HTTP traffic), execution identity = the `cur-importer` SA, deployed via Terraform (`terraform/run.tf`) with `image_tag` passed at apply time (`terraform apply -var="image_tag=<tag just pushed>"`).
- Cloud Scheduler job (`cur-bigquery-import-daily`, 06:00 UTC) hits the Cloud Run Jobs `run` API via a dedicated `cur-scheduler-invoker` SA holding `roles/run.invoker` on just this job.
- Monitoring: alert on job exit code ≠ 0, and a freshness check (e.g. a scheduled query asserting `MAX(usage_date)` in the table is within the last ~2 days) in case AWS silently stops exporting — **not yet set up**.

---

## Status

Parts 1–4 done and verified end-to-end; Part 5 deployed and manually confirmed working (3,137 rows loaded, $2,476.88 total cost across 20 environments on the first real run):

- ✅ Part 1: `cost-by-environment` export is live in AWS account `453829601976`, CSV.gz + `Manifest.json`.
- ✅ Part 2 + 3: Terraform applied — see `terraform/`. GCP SA, OIDC provider/role, BigQuery dataset/table.
- ✅ Part 4: `cloud_run_job/main.py` — row-level `MERGE` keyed on `usage_date` + `line_item_id`.
- ✅ Part 5: Cloud Run Job + Cloud Scheduler trigger deployed via `terraform/run.tf`, image in the shared `ufonia` Artifact Registry repo. Manually executed and confirmed working; the 06:00 UTC daily schedule hasn't fired on its own yet.
- ⬜ Freshness-check alerting (the one item in Part 5 not yet built).
