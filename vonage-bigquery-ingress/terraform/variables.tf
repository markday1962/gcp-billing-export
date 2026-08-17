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
