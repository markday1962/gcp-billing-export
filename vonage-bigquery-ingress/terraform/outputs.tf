output "vonage_importer_service_account_email" {
  value = google_service_account.vonage_importer.email
}

output "bq_dataset_id" {
  value = google_bigquery_dataset.vonage.dataset_id
}

output "bq_table_id" {
  value = google_bigquery_table.vonage_cost_and_usage.table_id
}

output "vonage_api_key_secret_id" {
  value = google_secret_manager_secret.vonage_api_key.secret_id
}

output "vonage_api_secret_secret_id" {
  value = google_secret_manager_secret.vonage_api_secret.secret_id
}
