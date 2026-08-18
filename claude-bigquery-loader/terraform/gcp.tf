# Part 2 — GCP side: service account, Secret Manager, BigQuery target
#
# secretmanager.googleapis.com is already enabled on this project (applied
# by vonage-bigquery-loader/terraform's state) — not re-declared here to
# avoid two Terraform states both claiming ownership of the same API
# enablement.

resource "google_service_account" "claude_importer" {
  project      = var.gcp_project_id
  account_id   = "claude-importer"
  display_name = "Claude Usage & Cost API importer"
  description  = "Runs the Cloud Run Job that pulls Anthropic's Usage & Cost Admin API data into BigQuery"
}

# Secret *container* only — no version is created here, so no credential
# material ever touches Terraform state or this repo. Add the real value
# with `gcloud secrets versions add` once it exists (see README Part 2).
resource "google_secret_manager_secret" "claude_admin_api_key" {
  project   = var.gcp_project_id
  secret_id = "claude-admin-api-key"

  replication {
    user_managed {
      replicas {
        location = var.gcp_region
      }
    }
  }
}

resource "google_secret_manager_secret_iam_member" "claude_importer_reads_admin_key" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.claude_admin_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.claude_importer.email}"
}

resource "google_bigquery_dataset" "claude" {
  project    = var.gcp_project_id
  dataset_id = var.bq_dataset_id
  location   = var.gcp_region
}

# One row per (day, model, workspace) — these are pre-aggregated dimension
# combinations from the API, not individual events, so there's no natural
# unique ID. Deduped on a hash of usage_date + every dimension field.
resource "google_bigquery_table" "claude_usage" {
  project             = var.gcp_project_id
  dataset_id          = google_bigquery_dataset.claude.dataset_id
  table_id            = var.bq_usage_table_id
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "usage_date"
  }

  schema = jsonencode([
    { name = "usage_date", type = "DATE", mode = "REQUIRED" },
    { name = "record_id", type = "STRING", mode = "REQUIRED" },
    { name = "bucket_start", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "bucket_end", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "account_id", type = "STRING", mode = "NULLABLE" },
    { name = "api_key_id", type = "STRING", mode = "NULLABLE" },
    { name = "workspace_id", type = "STRING", mode = "NULLABLE" },
    { name = "service_account_id", type = "STRING", mode = "NULLABLE" },
    { name = "model", type = "STRING", mode = "NULLABLE" },
    { name = "service_tier", type = "STRING", mode = "NULLABLE" },
    { name = "context_window", type = "STRING", mode = "NULLABLE" },
    { name = "inference_geo", type = "STRING", mode = "NULLABLE" },
    { name = "uncached_input_tokens", type = "INT64", mode = "NULLABLE" },
    { name = "cache_read_input_tokens", type = "INT64", mode = "NULLABLE" },
    { name = "cache_creation_ephemeral_5m_input_tokens", type = "INT64", mode = "NULLABLE" },
    { name = "cache_creation_ephemeral_1h_input_tokens", type = "INT64", mode = "NULLABLE" },
    { name = "output_tokens", type = "INT64", mode = "NULLABLE" },
    { name = "web_search_requests", type = "INT64", mode = "NULLABLE" },
  ])
}

# One row per (day, workspace, description) — same "aggregate, not event"
# reasoning as claude_usage. amount is stored as-is from the API; see
# README's open item about its cents-vs-dollars scale being unconfirmed.
resource "google_bigquery_table" "claude_cost" {
  project             = var.gcp_project_id
  dataset_id          = google_bigquery_dataset.claude.dataset_id
  table_id            = var.bq_cost_table_id
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "usage_date"
  }

  schema = jsonencode([
    { name = "usage_date", type = "DATE", mode = "REQUIRED" },
    { name = "record_id", type = "STRING", mode = "REQUIRED" },
    { name = "bucket_start", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "bucket_end", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "workspace_id", type = "STRING", mode = "NULLABLE" },
    { name = "description", type = "STRING", mode = "NULLABLE" },
    { name = "cost_type", type = "STRING", mode = "NULLABLE" },
    { name = "token_type", type = "STRING", mode = "NULLABLE" },
    { name = "model", type = "STRING", mode = "NULLABLE" },
    { name = "service_tier", type = "STRING", mode = "NULLABLE" },
    { name = "context_window", type = "STRING", mode = "NULLABLE" },
    { name = "inference_geo", type = "STRING", mode = "NULLABLE" },
    { name = "currency", type = "STRING", mode = "NULLABLE" },
    { name = "amount_usd", type = "FLOAT64", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_dataset_iam_member" "claude_importer_editor" {
  project    = var.gcp_project_id
  dataset_id = google_bigquery_dataset.claude.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.claude_importer.email}"
}

resource "google_project_iam_member" "claude_importer_job_user" {
  project = var.gcp_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.claude_importer.email}"
}
