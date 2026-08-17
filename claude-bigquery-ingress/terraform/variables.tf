variable "gcp_project_id" {
  description = "GCP project that hosts the Claude importer service account and BigQuery dataset"
  type        = string
  default     = "prj-ufonia-cmn-lon-billing-01"
}

variable "gcp_region" {
  description = "GCP region for BigQuery and Secret Manager replicas — must be an org-policy-allowed location"
  type        = string
  default     = "europe-west2"
}

variable "bq_dataset_id" {
  description = "BigQuery dataset for imported Claude usage/cost data"
  type        = string
  default     = "bq_dataset_claude_cost_and_usage"
}

variable "bq_usage_table_id" {
  description = "BigQuery table for Claude token usage data"
  type        = string
  default     = "claude_usage"
}

variable "bq_cost_table_id" {
  description = "BigQuery table for Claude USD cost data"
  type        = string
  default     = "claude_cost"
}
