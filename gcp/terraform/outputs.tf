output "cur_importer_service_account_email" {
  value = google_service_account.cur_importer.email
}

output "cur_bigquery_import_role_arn" {
  value = aws_iam_role.cur_bigquery_import.arn
}

output "google_oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.google.arn
}

output "bq_dataset_id" {
  value = google_bigquery_dataset.aws_cur.dataset_id
}

output "bq_table_id" {
  value = google_bigquery_table.aws_cost_and_usage.table_id
}

output "cur_bigquery_import_job_name" {
  value = google_cloud_run_v2_job.cur_bigquery_import.name
}

output "cur_bigquery_import_scheduler_job" {
  value = google_cloud_scheduler_job.cur_bigquery_import_daily.name
}
