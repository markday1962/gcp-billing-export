output "vonage_importer_service_account_email" {
  value = google_service_account.vonage_importer.email
}

output "bq_dataset_id" {
  value = google_bigquery_dataset.vonage.dataset_id
}

output "bq_table_id" {
  value = google_bigquery_table.vonage_cost_and_usage.table_id
}

output "vonage_master_api_keys_secret_id" {
  value = google_secret_manager_secret.vonage_master_api_keys.secret_id
}

output "vonage_bigquery_import_job_name" {
  value = google_cloud_run_v2_job.vonage_bigquery_import.name
}

output "vonage_bigquery_import_scheduler_job" {
  value = google_cloud_scheduler_job.vonage_bigquery_import_daily.name
}
