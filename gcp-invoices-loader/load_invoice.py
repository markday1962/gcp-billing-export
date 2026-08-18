"""Load a manual GCP invoice CSV (Cloud Console Billing > Reports export,
per-service monthly summary) into bq_dataset_billing_ufonia_invoice
.gcp_monthly_invoice_summary.

Why this exists: the live BigQuery billing export only has data from
2026-08-01 onward (Google doesn't backfill historical usage into it), so
prior months have to come from these manually-downloaded invoice CSVs
instead - same pattern vonage-bigquery-loader used before its Reports API
pipeline existed.

Usage: python3 load_invoice.py "Ufonia GCP Invoice Account_Reports, 2026-07-01 — 2026-07-31.csv"
(or with no argument, loads every *.csv in this folder)

Needs google-cloud-bigquery (bq load's own local-file upload path is
blocked by this org's VPC Service Controls policy - the client library's
load_table_from_json is not, so use that instead):
    python3 -m venv venv && venv/bin/pip install google-cloud-bigquery
    venv/bin/python load_invoice.py
"""

import csv
import glob
import re
import sys

from google.cloud import bigquery

PROJECT_ID = "prj-ufonia-cmn-lon-billing-01"
DATASET = "bq_dataset_billing_ufonia_invoice"
TABLE = "gcp_monthly_invoice_summary"

# Matches the target table's schema exactly - pinned explicitly so the
# staging load doesn't autodetect percent_change_vs_previous as FLOAT64
# on a month where every row happens to have a numeric-looking value
# (no "New" rows to force it to STRING).
STAGING_SCHEMA = [
    bigquery.SchemaField("invoice_month", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("service_description", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("service_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("list_cost", "FLOAT64"),
    bigquery.SchemaField("negotiated_savings", "FLOAT64"),
    bigquery.SchemaField("savings_programmes", "FLOAT64"),
    bigquery.SchemaField("other_savings", "FLOAT64"),
    bigquery.SchemaField("unrounded_subtotal", "FLOAT64"),
    bigquery.SchemaField("subtotal", "FLOAT64"),
    bigquery.SchemaField("percent_change_vs_previous", "STRING"),
]

DATE_RE = re.compile(r"(\d{4})-(\d{2})-\d{2}")


def invoice_month_from_filename(filename):
    match = DATE_RE.search(filename)
    if not match:
        raise ValueError(f"couldn't find a YYYY-MM-DD date in filename: {filename}")
    year, month = match.groups()
    return f"{year}-{month}-01"


def to_float(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_invoice_csv(path, invoice_month):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            service_id = (row.get("Service ID") or "").strip()
            if not service_id:
                continue  # footer rows (Subtotal/Tax/Filtered total) have no Service ID
            rows.append(
                {
                    "invoice_month": invoice_month,
                    "service_description": (row.get("Service description") or "").strip(),
                    "service_id": service_id,
                    "list_cost": to_float(row.get("List cost ($)")),
                    "negotiated_savings": to_float(row.get("Negotiated savings ($)")),
                    "savings_programmes": to_float(row.get("Savings programmes ($)")),
                    "other_savings": to_float(row.get("Other savings ($)")),
                    "unrounded_subtotal": to_float(row.get("Unrounded subtotal ($)")),
                    "subtotal": to_float(row.get("Subtotal ($)")),
                    "percent_change_vs_previous": (
                        row.get("Percent change in subtotal compared to previous period") or ""
                    ).strip()
                    or None,
                }
            )
    return rows


def load_and_merge(bq_client, rows, invoice_month):
    staging_table = f"{PROJECT_ID}.{DATASET}.{TABLE}_staging"
    target_table = f"{PROJECT_ID}.{DATASET}.{TABLE}"

    job_config = bigquery.LoadJobConfig(
        schema=STAGING_SCHEMA,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
    )
    job = bq_client.load_table_from_json(rows, staging_table, job_config=job_config)
    job.result()

    fields = [
        "service_description",
        "service_id",
        "list_cost",
        "negotiated_savings",
        "savings_programmes",
        "other_savings",
        "unrounded_subtotal",
        "subtotal",
        "percent_change_vs_previous",
    ]
    update_clause = ",\n        ".join(f"{f} = S.{f}" for f in fields)
    insert_cols = ", ".join(["invoice_month", *fields])
    insert_vals = ", ".join(f"S.{f}" for f in ["invoice_month", *fields])
    sql = f"""
    MERGE `{target_table}` T
    USING `{staging_table}` S
    ON T.invoice_month = S.invoice_month AND T.service_id = S.service_id
    WHEN MATCHED THEN UPDATE SET
        {update_clause}
    WHEN NOT MATCHED THEN INSERT ({insert_cols})
    VALUES ({insert_vals})
    """
    bq_client.query(sql).result()
    print(f"[{invoice_month}] {job.output_rows} service rows staged and merged into {target_table}")


def main():
    paths = sys.argv[1:] or glob.glob("*.csv")
    if not paths:
        print("no CSV files found")
        return
    bq_client = bigquery.Client(project=PROJECT_ID)
    for path in paths:
        invoice_month = invoice_month_from_filename(path)
        rows = parse_invoice_csv(path, invoice_month)
        load_and_merge(bq_client, rows, invoice_month)


if __name__ == "__main__":
    main()
