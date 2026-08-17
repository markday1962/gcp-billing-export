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

# Cloud Run's per-project service agent needs read access to the image in
# the centralized repo, since it lives in a different project.
resource "google_artifact_registry_repository_iam_member" "cur_importer_image_pull" {
  provider   = google.shared_services
  project    = var.image_repo_project
  location   = var.image_repo_location
  repository = var.image_repo_name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:service-${data.google_project.billing.number}@serverless-robot-prod.iam.gserviceaccount.com"

  depends_on = [google_project_service.run]
}

data "google_project" "billing" {
  project_id = var.gcp_project_id
}

resource "google_cloud_run_v2_job" "cur_bigquery_import" {
  project  = var.gcp_project_id
  name     = "cur-bigquery-import"
  location = var.gcp_run_region

  template {
    template {
      service_account = google_service_account.cur_importer.email
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
          value = google_bigquery_dataset.aws_cur.dataset_id
        }
        env {
          name  = "BQ_TABLE"
          value = google_bigquery_table.aws_cost_and_usage.table_id
        }
        env {
          name  = "GCP_SA_EMAIL"
          value = google_service_account.cur_importer.email
        }
        env {
          name  = "AWS_ROLE_ARN"
          value = aws_iam_role.cur_bigquery_import.arn
        }
        env {
          name  = "AWS_REGION"
          value = var.aws_region
        }
        env {
          name  = "CUR_BUCKET"
          value = var.cur_bucket_name
        }
        env {
          name  = "CUR_S3_PREFIX"
          value = var.cur_bucket_name
        }
        env {
          name  = "CUR_REPORT_NAME"
          value = var.cur_bucket_name
        }
      }
    }
  }

  depends_on = [
    google_project_service.run,
    google_artifact_registry_repository_iam_member.cur_importer_image_pull,
  ]
}

resource "google_service_account" "cur_scheduler_invoker" {
  project      = var.gcp_project_id
  account_id   = "cur-scheduler-invoker"
  display_name = "Invokes the cur-bigquery-import Cloud Run Job on a schedule"
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.gcp_project_id
  location = var.gcp_run_region
  name     = google_cloud_run_v2_job.cur_bigquery_import.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.cur_scheduler_invoker.email}"
}

resource "google_cloud_scheduler_job" "cur_bigquery_import_daily" {
  project   = var.gcp_project_id
  region    = var.gcp_run_region
  name      = "cur-bigquery-import-daily"
  schedule  = var.scheduler_cron
  time_zone = var.scheduler_time_zone

  http_target {
    http_method = "POST"
    uri         = "https://${var.gcp_run_region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.gcp_project_id}/jobs/${google_cloud_run_v2_job.cur_bigquery_import.name}:run"

    oauth_token {
      service_account_email = google_service_account.cur_scheduler_invoker.email
    }
  }

  depends_on = [google_project_service.cloudscheduler]
}
