variable "gcp_project_id" {
  description = "GCP project that hosts the CUR importer service account and BigQuery dataset"
  type        = string
  default     = "prj-ufonia-cmn-lon-billing-01"
}

variable "bq_dataset_id" {
  description = "BigQuery dataset for imported AWS Cost and Usage Report data"
  type        = string
  default     = "bg_dataset_aws_cost_and_usage"
}

variable "bq_dataset_location" {
  description = "BigQuery dataset location"
  type        = string
  default     = "europe-west2"
}

variable "bq_table_id" {
  description = "BigQuery table for imported AWS Cost and Usage Report data"
  type        = string
  default     = "aws_cost_and_usage"
}

variable "aws_account_id" {
  description = "AWS account that holds the CUR export bucket"
  type        = string
  default     = "453829601976"
}

variable "aws_region" {
  description = "AWS region for the CUR bucket and IAM resources"
  type        = string
  default     = "eu-west-2"
}

variable "aws_profile" {
  description = "Local AWS CLI/SSO profile used by Terraform to authenticate against the AWS account"
  type        = string
  default     = "AdministratorAccess-453829601976"
}

variable "cur_bucket_name" {
  description = "S3 bucket that AWS Data Exports (CUR) writes Parquet files to"
  type        = string
  default     = "cost-by-environment"
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
  description = "Image name within the Artifact Registry repo for the CUR importer"
  type        = string
  default     = "cur-bigquery-import"
}

variable "image_tag" {
  description = "Tag of the cur-bigquery-import image to deploy (set at apply time to the tag just pushed)"
  type        = string
}

variable "scheduler_cron" {
  description = "Cron schedule (in scheduler_time_zone) for the daily CUR import run"
  type        = string
  default     = "0 6 * * *"
}

variable "scheduler_time_zone" {
  description = "Time zone for scheduler_cron"
  type        = string
  default     = "Etc/UTC"
}
