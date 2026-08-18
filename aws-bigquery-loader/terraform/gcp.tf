# Part 3 — GCP side: service account and BigQuery target

resource "google_service_account" "cur_importer" {
  project      = var.gcp_project_id
  account_id   = "cur-importer"
  display_name = "AWS CUR importer"
  description  = "Runs the Cloud Run Job that pulls AWS Cost and Usage Report data into BigQuery via AWS OIDC federation"
}

resource "google_bigquery_dataset" "aws_cur" {
  project    = var.gcp_project_id
  dataset_id = var.bq_dataset_id
  location   = var.bq_dataset_location
}

# Schema derived from a real export landing in the `cost-by-environment`
# CUR 2.0 bucket (204 columns total). The full column set is mostly sparse
# per-SKU product attributes (instance type, memory, storage class, etc.)
# that aren't useful for cost reporting — this loads the identity/billing/
# cost fields plus the two tags that give the bucket its name:
# resourceTags/user:environment and the costCategory/* dimensions.
# See "Status" in ../README.md.
resource "google_bigquery_table" "aws_cost_and_usage" {
  project             = var.gcp_project_id
  dataset_id          = google_bigquery_dataset.aws_cur.dataset_id
  table_id            = var.bq_table_id
  deletion_protection = false

  time_partitioning {
    type  = "DAY"
    field = "usage_date"
  }

  schema = jsonencode([
    { name = "usage_date", type = "DATE", mode = "REQUIRED" },                               # derived from lineItem/UsageStartDate
    { name = "line_item_id", type = "STRING", mode = "REQUIRED" },                           # identity/LineItemId — MERGE dedup key
    { name = "bill_payer_account_id", type = "STRING", mode = "NULLABLE" },                  # bill/PayerAccountId
    { name = "bill_billing_period_start_date", type = "DATE", mode = "NULLABLE" },           # bill/BillingPeriodStartDate
    { name = "line_item_usage_account_id", type = "STRING", mode = "NULLABLE" },             # lineItem/UsageAccountId
    { name = "line_item_type", type = "STRING", mode = "NULLABLE" },                         # lineItem/LineItemType
    { name = "line_item_usage_start_date", type = "TIMESTAMP", mode = "NULLABLE" },          # lineItem/UsageStartDate
    { name = "line_item_usage_end_date", type = "TIMESTAMP", mode = "NULLABLE" },            # lineItem/UsageEndDate
    { name = "line_item_product_code", type = "STRING", mode = "NULLABLE" },                 # lineItem/ProductCode
    { name = "line_item_usage_type", type = "STRING", mode = "NULLABLE" },                   # lineItem/UsageType
    { name = "line_item_operation", type = "STRING", mode = "NULLABLE" },                    # lineItem/Operation
    { name = "line_item_description", type = "STRING", mode = "NULLABLE" },                  # lineItem/LineItemDescription
    { name = "line_item_usage_amount", type = "FLOAT64", mode = "NULLABLE" },                # lineItem/UsageAmount
    { name = "line_item_unblended_rate", type = "FLOAT64", mode = "NULLABLE" },              # lineItem/UnblendedRate
    { name = "line_item_unblended_cost", type = "FLOAT64", mode = "NULLABLE" },              # lineItem/UnblendedCost
    { name = "product_name", type = "STRING", mode = "NULLABLE" },                           # product/ProductName
    { name = "product_service_code", type = "STRING", mode = "NULLABLE" },                   # product/servicecode
    { name = "product_region", type = "STRING", mode = "NULLABLE" },                         # product/region
    { name = "pricing_unit", type = "STRING", mode = "NULLABLE" },                           # pricing/unit
    { name = "reservation_effective_cost", type = "FLOAT64", mode = "NULLABLE" },            # reservation/EffectiveCost
    { name = "savings_plan_effective_cost", type = "FLOAT64", mode = "NULLABLE" },           # savingsPlan/SavingsPlanEffectiveCost
    { name = "resource_tags_environment", type = "STRING", mode = "NULLABLE" },              # resourceTags/user:environment
    { name = "resource_tags_transfer_custom_hostname", type = "STRING", mode = "NULLABLE" }, # resourceTags/user:transfer:customHostname
    { name = "cost_category_development", type = "STRING", mode = "NULLABLE" },              # costCategory/Development
    { name = "cost_category_production", type = "STRING", mode = "NULLABLE" },               # costCategory/Production
  ])
}

resource "google_bigquery_dataset_iam_member" "cur_importer_editor" {
  project    = var.gcp_project_id
  dataset_id = google_bigquery_dataset.aws_cur.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.cur_importer.email}"
}

resource "google_project_iam_member" "cur_importer_job_user" {
  project = var.gcp_project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.cur_importer.email}"
}
