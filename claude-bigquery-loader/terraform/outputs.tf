output "claude_importer_service_account_email" {
  value = google_service_account.claude_importer.email
}

output "bq_dataset_id" {
  value = google_bigquery_dataset.claude.dataset_id
}

output "bq_usage_table_id" {
  value = google_bigquery_table.claude_usage.table_id
}

output "bq_cost_table_id" {
  value = google_bigquery_table.claude_cost.table_id
}

output "claude_admin_api_key_secret_id" {
  value = google_secret_manager_secret.claude_admin_api_key.secret_id
}
