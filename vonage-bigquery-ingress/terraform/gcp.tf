# Part 2 — GCP side: service account, Secret Manager, BigQuery target

resource "google_project_service" "secretmanager" {
  project            = var.gcp_project_id
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_service_account" "vonage_importer" {
  project      = var.gcp_project_id
  account_id   = "vonage-importer"
  display_name = "Vonage Reports API importer"
  description  = "Runs the Cloud Run Job that pulls Vonage Reports API data into BigQuery"
}

# Secret *containers* only — no version is created here, so no credential
# material ever touches Terraform state or this repo. Add the real values
# with `gcloud secrets versions add` once they exist (see README Part 2).
resource "google_secret_manager_secret" "vonage_api_key" {
  project   = var.gcp_project_id
  secret_id = "vonage-api-key"

  replication {
    user_managed {
      replicas {
        location = var.gcp_region
      }
    }
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "vonage_api_secret" {
  project   = var.gcp_project_id
  secret_id = "vonage-api-secret"

  replication {
    user_managed {
      replicas {
        location = var.gcp_region
      }
    }
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_iam_member" "vonage_importer_reads_api_key" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.vonage_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.vonage_importer.email}"
}

resource "google_secret_manager_secret_iam_member" "vonage_importer_reads_api_secret" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.vonage_api_secret.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.vonage_importer.email}"
}

resource "google_bigquery_dataset" "vonage" {
  project    = var.gcp_project_id
  dataset_id = var.bq_dataset_id
  location   = var.gcp_region
}

# Schema deliberately hybrid: a handful of well-known fields (confirmed from
# Vonage's documented SMS CSV schema) as typed columns, plus a `raw` JSON
# catch-all for everything else — Voice/WebSocket CDR column names are not
# publicly documented and haven't been verified against a real report yet.
# See README "Status" before trusting record_id/usage_date derivation.
resource "google_bigquery_table" "vonage_cost_and_usage" {
  project             = var.gcp_project_id
  dataset_id          = google_bigquery_dataset.vonage.dataset_id
  table_id            = var.bq_table_id
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "usage_date"
  }

  schema = jsonencode([
    { name = "usage_date", type = "DATE", mode = "REQUIRED" },
    { name = "record_id", type = "STRING", mode = "REQUIRED" }, # dedup key — see README caveat
    { name = "product", type = "STRING", mode = "REQUIRED" },   # the Reports API product this came from, e.g. SMS
    { name = "direction", type = "STRING", mode = "NULLABLE" }, # inbound/outbound
    { name = "category", type = "STRING", mode = "REQUIRED" },  # SMS / Inbound Calls / Outbound Calls / WebSocket / Other
    { name = "total_price", type = "FLOAT64", mode = "NULLABLE" },
    { name = "currency", type = "STRING", mode = "NULLABLE" },
    { name = "network", type = "STRING", mode = "NULLABLE" },
    { name = "country", type = "STRING", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE" },
    { name = "raw", type = "JSON", mode = "NULLABLE" }, # full raw CSV row, for fields not promoted above
  ])
}

resource "google_bigquery_dataset_iam_member" "vonage_importer_editor" {
  project    = var.gcp_project_id
  dataset_id = google_bigquery_dataset.vonage.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.vonage_importer.email}"
}

resource "google_project_iam_member" "vonage_importer_job_user" {
  project = var.gcp_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.vonage_importer.email}"
}
