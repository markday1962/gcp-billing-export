# Part 5 — deploy the Cloud Run Job and its daily Cloud Scheduler trigger.

resource "google_project_service" "run" {
  project            = var.gcp_project_id
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudscheduler" {
  project            = var.gcp_project_id
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

locals {
  image = "${var.image_repo_location}-docker.pkg.dev/${var.image_repo_project}/${var.image_repo_name}/${var.image_name}:${var.image_tag}"
}

data "google_project" "billing" {
  project_id = var.gcp_project_id
}

# Cloud Run's per-project service agent needs read access to the image in
# the centralized repo, since it lives in a different project.
resource "google_artifact_registry_repository_iam_member" "vonage_importer_image_pull" {
  provider   = google.shared_services
  project    = var.image_repo_project
  location   = var.image_repo_location
  repository = var.image_repo_name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:service-${data.google_project.billing.number}@serverless-robot-prod.iam.gserviceaccount.com"

  depends_on = [google_project_service.run]
}

resource "google_cloud_run_v2_job" "vonage_bigquery_import" {
  project  = var.gcp_project_id
  name     = "vonage-bigquery-import"
  location = var.gcp_run_region

  template {
    template {
      service_account = google_service_account.vonage_importer.email
      timeout         = "900s"
      max_retries     = 1

      containers {
        image = local.image

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        env {
          name  = "GCP_PROJECT_ID"
          value = var.gcp_project_id
        }
        env {
          name  = "BQ_DATASET"
          value = google_bigquery_dataset.vonage.dataset_id
        }
        env {
          name  = "BQ_TABLE"
          value = google_bigquery_table.vonage_cost_and_usage.table_id
        }
        env {
          name = "VONAGE_CREDS_JSON"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.vonage_master_api_keys.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.run,
    google_artifact_registry_repository_iam_member.vonage_importer_image_pull,
  ]
}

resource "google_service_account" "vonage_scheduler_invoker" {
  project      = var.gcp_project_id
  account_id   = "vonage-scheduler-invoker"
  display_name = "Invokes the vonage-bigquery-import Cloud Run Job on a schedule"
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.gcp_project_id
  location = var.gcp_run_region
  name     = google_cloud_run_v2_job.vonage_bigquery_import.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.vonage_scheduler_invoker.email}"
}

resource "google_cloud_scheduler_job" "vonage_bigquery_import_daily" {
  project   = var.gcp_project_id
  region    = var.gcp_run_region
  name      = "vonage-bigquery-import-daily"
  schedule  = var.scheduler_cron
  time_zone = var.scheduler_time_zone

  http_target {
    http_method = "POST"
    uri         = "https://${var.gcp_run_region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.gcp_project_id}/jobs/${google_cloud_run_v2_job.vonage_bigquery_import.name}:run"

    oauth_token {
      service_account_email = google_service_account.vonage_scheduler_invoker.email
    }
  }

  depends_on = [google_project_service.cloudscheduler]
}
