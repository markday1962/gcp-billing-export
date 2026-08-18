variable "gcp_project_id" {
  description = "GCP project that hosts the Vonage importer service account and BigQuery dataset"
  type        = string
  default     = "prj-ufonia-cmn-lon-billing-01"
}

variable "bq_dataset_id" {
  description = "BigQuery dataset for imported Vonage Reports API data"
  type        = string
  default     = "bq_dataset_vonage_cost_and_usage"
}

variable "gcp_region" {
  description = "GCP region for BigQuery, Secret Manager replicas, and (later) Cloud Run — must be an org-policy-allowed location"
  type        = string
  default     = "europe-west2"
}

variable "bq_table_id" {
  description = "BigQuery table for imported Vonage Reports API data"
  type        = string
  default     = "vonage_cost_and_usage"
}

variable "gcp_run_region" {
  description = "Region for the Cloud Run Job and Cloud Scheduler trigger"
  type        = string
  default     = "europe-west2"
}

variable "image_repo_project" {
  description = "GCP project hosting the centralized Artifact Registry repo"
  type        = string
  default     = "prj-ufonia-dev-lon-svc-01"
}

variable "image_repo_location" {
  description = "Location of the centralized Artifact Registry repo"
  type        = string
  default     = "europe-west2"
}

variable "image_repo_name" {
  description = "Name of the centralized Artifact Registry Docker repo"
  type        = string
  default     = "ufonia"
}

variable "image_name" {
  description = "Image name within the Artifact Registry repo for the Vonage importer"
  type        = string
  default     = "vonage-bigquery-import"
}

variable "image_tag" {
  description = "Tag of the vonage-bigquery-import image to deploy (set at apply time to the tag just pushed)"
  type        = string
}

variable "scheduler_cron" {
  description = "Cron schedule (in scheduler_time_zone) for the daily Vonage import run"
  type        = string
  default     = "0 7 * * *"
}

variable "scheduler_time_zone" {
  description = "Time zone for scheduler_cron"
  type        = string
  default     = "Etc/UTC"
}
